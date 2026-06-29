"""
crawl_service_v2.py — 이벤트 기반 파이프라인 (요구사항 7)
================================================================
crawl → extract → snapshot → diff → classify → event → (notify) → UI

기존 crawl_service.py 를 대체. 새 모듈 사용:
  - config.registry         (확장 가능 URL/타겟 + 정책)
  - crawler.hybrid_crawler  (httpx 우선, Playwright 폴백)
  - engines.diff_engine     (L0~L5, char/token/DOM, phash)
  - engines.intel_engine    (할루시네이션 차단 분석)

핵심: '이전 스냅샷'을 page_snapshots 테이블에서 URL 단위로 읽어 diff.
      변경 유무와 무관하게 항상 intel 분석을 돌려 '현황 분석' 제공(요구사항).
      DB 는 sync(SessionLocal) 사용 — 기존 코드와 동일 패턴. 단, 블로킹 최소화 위해
      네트워크(크롤)는 async, DB I/O 는 짧게.
"""

from __future__ import annotations
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List

from loguru import logger
from sqlalchemy import text

from config import (
    SEED_TARGETS, load_active_urls, tier_for_url, target_for_url,
)
from crawler import HybridCrawler
from diff_engine import (
    DiffEngine, structural_signature, summarize_events,
)
from intel_engine import IntelEngine, aeo_facts


def _s(v) -> str:
    return v if isinstance(v, str) else ("" if v is None else str(v))


def _content_hash(page: Dict[str, Any]) -> str:
    import hashlib
    blob = "|".join(_s(page.get(k)) for k in ("title", "h1", "meta_description", "body_content"))
    return hashlib.sha1(blob.encode("utf-8", "ignore")).hexdigest()


class CrawlServiceV2:
    def __init__(self, session_local, sync_engine, progress: Dict[str, Any] = None):
        """
        session_local : database.database.SessionLocal (sync sessionmaker)
        sync_engine   : database.database.sync_engine (raw SQL 용)
        progress      : main.py 의 crawl_state dict (SSE 진행률 push)
        """
        self.SessionLocal = session_local
        self.sync_engine = sync_engine
        self.progress = progress if progress is not None else {}
        self.intel = IntelEngine()

    # ── 진행률 push (SSE) ───────────────────────────────────
    def _emit(self, **kw):
        ev = {"ts": datetime.utcnow().isoformat(), **kw}
        self.progress.setdefault("events", []).append(ev)

    # ── 메인 엔트리 ─────────────────────────────────────────
    async def execute_crawl(self, site_key: str) -> Dict[str, Any]:
        target = SEED_TARGETS.get(site_key)
        if not target:
            raise ValueError(f"unknown site: {site_key}")

        run_id = f"{site_key}_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
        db_urls = self._load_db_urls(site_key)
        urls = load_active_urls(site_key, db_urls)
        logger.info(f"[{run_id}] start {site_key}: {len(urls)} urls")
        self._emit(type="start", run_id=run_id, total=len(urls), site=site_key)

        # run 레코드
        self._exec("""INSERT INTO crawl_runs (crawl_run_id, site_name, started_at, status, total_urls_discovered)
                      VALUES (:r,:s,:t,'running',:n)""",
                   r=run_id, s=site_key, t=datetime.utcnow(), n=len(urls))

        crawler = HybridCrawler()
        await crawler.start()
        crawled: List[Dict[str, Any]] = []
        all_events = []
        try:
            for entry in urls:
                url = entry["url"]
                tier = entry["tier_level"]
                requires_js = target.extraction.requires_js
                try:
                    page = await crawler.crawl(url, requires_js=requires_js)
                except Exception as e:
                    self._emit(type="page_done", url=url, site=target.display_name,
                               tier=f"Tier {tier}", status="error", error=str(e))
                    continue
                if page.get("error"):
                    self._emit(type="page_done", url=url, site=target.display_name,
                               tier=f"Tier {tier}", status="error", error=page["error"])
                    continue

                page["site_key"] = site_key
                page["tier_level"] = tier
                crawled.append(page)

                # extract → snapshot(save) → diff(vs previous) → events
                prev = self._load_previous_snapshot(url)
                events = self._diff(url, site_key, tier, page, prev, target)
                self._save_snapshot(run_id, site_key, url, page)
                for ev in events:
                    self._save_event(run_id, ev)
                all_events.extend(events)

                self._emit(type="page_done", url=url, site=target.display_name,
                           tier=f"Tier {tier}", status="success",
                           title=page.get("title"), changes=len(events))

            # 집계 + 현황 분석 (변경 유무 무관)
            summary = summarize_events([e for e in all_events])
            self._run_intel(run_id, site_key, target, crawled,
                            [e.to_dict() for e in all_events], summary["max_level"])

            self._exec("""UPDATE crawl_runs SET status='completed', completed_at=:t,
                          total_urls_crawled=:c, total_changes_detected=:ch
                          WHERE crawl_run_id=:r""",
                       t=datetime.utcnow(), c=len(crawled), ch=len(all_events), r=run_id)
            self._emit(type="done", run_id=run_id)
            logger.info(f"[{run_id}] done: {len(crawled)} pages, {len(all_events)} events, max={summary['max_level']}")
            return {"crawl_run_id": run_id, "site_name": site_key, "status": "completed",
                    "urls_crawled": len(crawled), "changes_detected": len(all_events),
                    "max_level": summary["max_level"], "by_level": summary["by_level"]}
        except Exception as e:
            logger.error(f"[{run_id}] failed: {e}")
            self._exec("UPDATE crawl_runs SET status='failed', error_message=:m WHERE crawl_run_id=:r",
                       m=_s(e)[:480], r=run_id)
            self._emit(type="done", run_id=run_id, error=str(e))
            return {"crawl_run_id": run_id, "status": "failed", "error": _s(e)}
        finally:
            await crawler.close()

    # ── diff ────────────────────────────────────────────────
    def _diff(self, url, site_key, tier, page, prev, target):
        if not prev:
            return []          # 최초 크롤 → 기준점만 저장, 변화 없음
        eng = DiffEngine(critical_keywords=target.sensitivity.critical_keywords,
                         min_diff_ratio=target.sensitivity.min_text_diff_ratio)
        # 이전 구조 지문 주입 (저장돼 있으면 재계산 회피)
        prev["_sig"] = prev.get("_sig") or {}
        return eng.detect(url, site_key, tier, page, prev)

    # ── intel (현황/변화 분석, 근거기반) ─────────────────────
    def _run_intel(self, run_id, site_key, target, pages, event_dicts, max_level):
        try:
            res = self.intel.analyze_site(
                site_display=target.display_name, is_ours=target.is_ours,
                pages=pages, change_events=event_dicts, max_level=max_level)
            # POV 테이블에 1행 저장 (기존 UI 호환)
            self._exec("""INSERT INTO povs
                (pov_run_id, related_crawl_run_id, observation, hypothesis, opportunity,
                 recommended_action, priority, functional_area, created_at)
                VALUES (:p,:r,:o,:h,:op,:a,:pr,:fa,:c)""",
                p=f"pov_{run_id}", r=run_id,
                o=_s(res.get("summary"))[:1900],
                h=_s(res.get("aeo_implications_for_samsung"))[:1900],
                op=_s(json.dumps(res.get("insights", []), ensure_ascii=False))[:1900],
                a=_s(json.dumps(res.get("action_items", []), ensure_ascii=False))[:1900],
                pr="high" if max_level in ("L4", "L5") else "medium",
                fa="AEO", c=datetime.utcnow())
        except Exception as e:
            logger.warning(f"intel save failed: {e}")

    # ── snapshot I/O ────────────────────────────────────────
    def _load_previous_snapshot(self, url) -> Dict[str, Any]:
        try:
            with self.sync_engine.connect() as conn:
                row = conn.execute(text("""
                    SELECT title,h1,meta_description,canonical_url,body_content,
                           structural_signature,screenshot_phash
                    FROM page_snapshots WHERE url=:u ORDER BY crawled_at DESC LIMIT 1
                """), {"u": url}).fetchone()
            if not row:
                return {}
            sig = {}
            try:
                sig = json.loads(row[5]) if row[5] else {}
            except Exception:
                sig = {}
            return {"title": row[0], "h1": row[1], "meta_description": row[2],
                    "canonical_url": row[3], "body_content": row[4],
                    "_sig": sig, "screenshot_phash": row[6]}
        except Exception as e:
            logger.warning(f"load snapshot skip {url}: {e}")
            return {}

    def _save_snapshot(self, run_id, site_key, url, page):
        try:
            sig = structural_signature(page)
            self._exec("""INSERT INTO page_snapshots
                (crawl_run_id, url, site_key, title, h1, meta_description, canonical_url,
                 body_content, structural_signature, screenshot_phash, screenshot_thumb,
                 content_hash, word_count, crawled_at)
                VALUES (:r,:u,:s,:t,:h1,:md,:cu,:bc,:sig,:ph,:thumb,:chash,:wc,:ts)""",
                r=run_id, u=url, s=site_key,
                t=_s(page.get("title"))[:1000], h1=_s(page.get("h1"))[:2000],
                md=_s(page.get("meta_description"))[:2000], cu=_s(page.get("canonical_url"))[:1000],
                bc=_s(page.get("body_content"))[:120000],
                sig=json.dumps(sig, ensure_ascii=False)[:8000],
                ph=page.get("screenshot_phash"), thumb=page.get("screenshot_thumb"),
                chash=_content_hash(page),
                wc=int(page.get("word_count") or 0), ts=datetime.utcnow())
        except Exception as e:
            logger.warning(f"save snapshot skip {url}: {e}")

    def _save_event(self, run_id, ev):
        try:
            self._exec("""INSERT INTO detected_changes
                (crawl_run_id, url, change_type, change_category, field_name,
                 before_value, after_value, severity, severity_level, severity_reason,
                 summary, char_added, char_removed, diff_ratio, evidence, tier_level, detected_at)
                VALUES (:r,:u,:ct,:cc,:fn,:bv,:av,:sev,:lv,:sr,:sm,:ca,:cr,:dr,:evd,:tl,:ts)""",
                r=run_id, u=ev.url, ct=ev.change_type, cc=ev.severity_level, fn=ev.field_name,
                bv=ev.before_value, av=ev.after_value,
                sev=ev.severity_legacy, lv=ev.severity_level, sr=ev.summary, sm=ev.summary,
                ca=ev.char_added, cr=ev.char_removed, dr=ev.diff_ratio,
                evd=json.dumps(ev.evidence, ensure_ascii=False)[:2000],
                tl=ev.tier_level, ts=ev.detected_at)
        except Exception as e:
            logger.warning(f"save event skip: {e}")

    # ── DB 헬퍼 ─────────────────────────────────────────────
    def _exec(self, sql, **params):
        try:
            with self.sync_engine.connect() as conn:
                conn.execute(text(sql), params)
                conn.commit()
        except Exception as e:
            logger.warning(f"sql skip: {e}")

    def _load_db_urls(self, site_key) -> List[str]:
        try:
            with self.sync_engine.connect() as conn:
                rows = conn.execute(text(
                    "SELECT url FROM monitored_urls WHERE enabled=true AND site_key=:s"),
                    {"s": site_key}).fetchall()
            return [r[0] for r in rows]
        except Exception:
            return []
