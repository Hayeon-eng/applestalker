
"""
crawl_service_v2.py — 이벤트 기반 파이프라인 (안정화 + 디버그 유지 버전)
================================================================
✔ 기존 구조 100% 유지
✔ 0 pages → DELETE RUN 제거 (디버깅 가능)
✔ 실패해도 run 유지
✔ AEO 분석 유지
✔ [FIX] _load_db_urls: SEED URL + DB URL 머지 (load_active_urls 활용)
"""

from __future__ import annotations
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List

from loguru import logger
from sqlalchemy import text

from config import SEED_TARGETS, load_active_urls, tier_for_url, target_for_url
from crawler import HybridCrawler
from diff_engine import DiffEngine, structural_signature, summarize_events
from intel_engine import IntelEngine, aeo_facts


def _s(v) -> str:
    return v if isinstance(v, str) else ("" if v is None else str(v))


def _content_hash(page: Dict[str, Any]) -> str:
    import hashlib
    blob = "|".join(_s(page.get(k)) for k in ("title", "h1", "meta_description", "body_content"))
    return hashlib.sha1(blob.encode("utf-8", "ignore")).hexdigest()


class CrawlServiceV2:
    def __init__(self, session_local, sync_engine, progress: Dict[str, Any] = None):
        self.SessionLocal = session_local
        self.sync_engine = sync_engine
        self.progress = progress if progress is not None else {}
        self.intel = IntelEngine()

    # ─────────────────────────────────────────────
    # SSE EVENT
    # ─────────────────────────────────────────────
    def _emit(self, **kw):
        ev = {"ts": datetime.utcnow().isoformat(), **kw}
        self.progress.setdefault("events", []).append(ev)

    # ─────────────────────────────────────────────
    # MAIN
    # ─────────────────────────────────────────────
    async def execute_crawl(self, site_key: str) -> Dict[str, Any]:
        target = SEED_TARGETS.get(site_key)
        if not target:
            raise ValueError(f"unknown site: {site_key}")

        run_id = f"{site_key}_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
        urls = self._load_db_urls(site_key)

        logger.info(f"[{run_id}] start {site_key}: {len(urls)} urls")
        self._emit(type="start", run_id=run_id, total=len(urls), site=site_key)

        # run 생성
        self._exec("""
            INSERT INTO crawl_runs
            (crawl_run_id, site_name, started_at, status, total_urls_discovered)
            VALUES (:r,:s,:t,'running',:n)
        """, r=run_id, s=site_key, t=datetime.utcnow(), n=len(urls))

        crawler = HybridCrawler()
        await crawler.start()

        crawled: List[Dict[str, Any]] = []
        all_events = []

        try:
            for entry in urls:
                url = entry["url"]
                tier = entry["tier_level"]

                try:
                    page = await crawler.crawl(url, requires_js=target.extraction.requires_js)
                except Exception as e:
                    self._emit(type="page_done", url=url, status="error", error=str(e))
                    continue

                if not page or page.get("error"):
                    self._emit(type="page_done", url=url, status="error", error=page.get("error"))
                    continue

                page["site_key"] = site_key
                page["tier_level"] = tier
                crawled.append(page)

                prev = self._load_previous_snapshot(url)
                events = self._diff(url, site_key, tier, page, prev, target)

                self._save_snapshot(run_id, site_key, url, page)

                for ev in events:
                    self._save_event(run_id, ev)

                all_events.extend(events)

                self._emit(
                    type="page_done",
                    url=url,
                    status="success",
                    changes=len(events),
                )

            # ─────────────────────────────────────────────
            # INTEL (항상 실행)
            # ─────────────────────────────────────────────
            summary = summarize_events(all_events)

            self._run_intel(
                run_id,
                site_key,
                target,
                crawled,
                [e.to_dict() for e in all_events],
                summary["max_level"] if all_events else "L0"
            )

            # ─────────────────────────────────────────────
            # RUN UPDATE
            # ─────────────────────────────────────────────
            self._exec("""
                UPDATE crawl_runs
                SET status='completed',
                    completed_at=:t,
                    total_urls_crawled=:c,
                    total_changes_detected=:ch
                WHERE crawl_run_id=:r
            """,
            t=datetime.utcnow(),
            c=len(crawled),
            ch=len(all_events),
            r=run_id)

            # ❗❗ 중요 수정: DELETE RUN 제거 (디버깅 가능하게 유지)
            if len(crawled) == 0:
                logger.warning(f"[{run_id}] 0 pages crawled → KEEP RUN for debugging")

            self._emit(type="done", run_id=run_id)

            return {
                "crawl_run_id": run_id,
                "status": "completed",
                "urls_crawled": len(crawled),
                "changes_detected": len(all_events),
            }

        except Exception as e:
            logger.error(f"[{run_id}] failed: {e}")

            self._exec("""
                UPDATE crawl_runs
                SET status='failed',
                    error_message=:m
                WHERE crawl_run_id=:r
            """, m=_s(e)[:480], r=run_id)

            self._emit(type="done", run_id=run_id, error=str(e))

            return {
                "crawl_run_id": run_id,
                "status": "failed",
                "error": _s(e)
            }

        finally:
            await crawler.close()

    # ─────────────────────────────────────────────
    # DIFF
    # ─────────────────────────────────────────────
    def _diff(self, url, site_key, tier, page, prev, target):
        if not prev:
            return []

        eng = DiffEngine(
            critical_keywords=target.sensitivity.critical_keywords,
            min_diff_ratio=target.sensitivity.min_text_diff_ratio
        )

        prev["_sig"] = prev.get("_sig") or {}
        return eng.detect(url, site_key, tier, page, prev)

    # ─────────────────────────────────────────────
    # INTEL
    # ─────────────────────────────────────────────
    def _run_intel(self, run_id, site_key, target, pages, event_dicts, max_level):
        """
        [PHASE1 변경] analyze_site()가 이제 {"data":..,"copy":..,"visual":..} 구조로
        반환되므로, povs 테이블의 신규 컬럼(data_analysis/copy_analysis/visual_analysis)에
        각각 분리 저장. 기존 observation/hypothesis/opportunity 는 이메일 등 하위호환용으로
        요약만 채워 유지.
        """
        try:
            res = self.intel.analyze_site(
                site_display=target.display_name,
                is_ours=target.is_ours,
                pages=pages,
                change_events=event_dicts,
                max_level=max_level
            )

            data_b = res.get("data", {})
            copy_b = res.get("copy", {})
            visual_b = res.get("visual", {})

            # 하위호환 필드(이메일 리포트 등에서 사용)
            legacy_insights = (data_b.get("insights", []) + copy_b.get("insights", []) +
                               visual_b.get("insights", []))[:10]

            self._exec("""
                INSERT INTO povs
                (pov_run_id, related_crawl_run_id, observation, hypothesis,
                 opportunity, recommended_action, priority, functional_area,
                 data_analysis, copy_analysis, visual_analysis, created_at)
                VALUES (:p,:r,:o,:h,:op,:a,:pr,:fa,:da,:co,:vi,:c)
            """,
            p=f"pov_{run_id}",
            r=run_id,
            o=_s(res.get("summary"))[:1900],
            h="",
            op=_s(json.dumps(legacy_insights, ensure_ascii=False))[:1900],
            a="[]",
            pr="high" if max_level in ("L4", "L5") else "medium",
            fa="DATA/COPY/VISUAL",
            da=json.dumps(data_b, ensure_ascii=False)[:200000],
            co=json.dumps(copy_b, ensure_ascii=False)[:200000],
            vi=json.dumps(visual_b, ensure_ascii=False)[:200000],
            c=datetime.utcnow())

        except Exception as e:
            logger.warning(f"intel save failed: {e}")

    # ─────────────────────────────────────────────
    # SNAPSHOT / EVENT (그대로 유지)
    # ─────────────────────────────────────────────
    def _load_previous_snapshot(self, url):
        try:
            with self.sync_engine.connect() as conn:
                row = conn.execute(text("""
                    SELECT title,h1,meta_description,canonical_url,body_content,
                           structural_signature,screenshot_phash
                    FROM page_snapshots
                    WHERE url=:u
                    ORDER BY crawled_at DESC
                    LIMIT 1
                """), {"u": url}).fetchone()

            if not row:
                return {}

            sig = json.loads(row[5]) if row[5] else {}

            return {
                "title": row[0],
                "h1": row[1],
                "meta_description": row[2],
                "canonical_url": row[3],
                "body_content": row[4],
                "_sig": sig,
                "screenshot_phash": row[6]
            }

        except Exception as e:
            logger.warning(f"snapshot load failed: {e}")
            return {}

    def _save_snapshot(self, run_id, site_key, url, page):
        """
        [PHASE1 변경] DATA/COPY/VISUAL 상세 분석에 필요한 원본(JSON-LD, h2/h3,
        이미지, FAQ, 내비, CTA)을 함께 영구 저장. 기존엔 이 데이터가 크롤
        도중에만 메모리에 존재하고 버려져서, 크롤 끝난 뒤 페이지를 클릭해도
        근거 데이터가 DB에 없어 상세를 재구성할 수 없었음.
        """
        try:
            sig = structural_signature(page)

            self._exec("""
                INSERT INTO page_snapshots
                (crawl_run_id, url, site_key, title, h1, meta_description,
                 canonical_url, body_content, structural_signature,
                 screenshot_phash, screenshot_thumb, content_hash,
                 word_count, raw_h2, raw_h3, raw_structured_data,
                 raw_faqs, raw_images, raw_navigation, raw_ctas, crawled_at)
                VALUES (:r,:u,:s,:t,:h1,:md,:cu,:bc,:sig,:ph,:thumb,:ch,:wc,
                        :h2,:h3,:sd,:faqs,:img,:nav,:cta,:ts)
            """,
            r=run_id, u=url, s=site_key,
            t=_s(page.get("title")),
            h1=_s(page.get("h1")),
            md=_s(page.get("meta_description")),
            cu=_s(page.get("canonical_url")),
            bc=_s(page.get("body_content")),
            sig=json.dumps(sig),
            ph=page.get("screenshot_phash"),
            thumb=page.get("screenshot_thumb"),
            ch=_content_hash(page),
            wc=int(page.get("word_count") or 0),
            h2=json.dumps(page.get("h2") or [], ensure_ascii=False),
            h3=json.dumps(page.get("h3") or [], ensure_ascii=False),
            sd=json.dumps(page.get("structured_data") or [], ensure_ascii=False)[:200000],
            faqs=json.dumps(page.get("faqs") or [], ensure_ascii=False)[:50000],
            img=json.dumps(page.get("images") or [], ensure_ascii=False)[:50000],
            nav=json.dumps(page.get("navigation") or {}, ensure_ascii=False)[:20000],
            cta=json.dumps(page.get("ctas") or [], ensure_ascii=False)[:20000],
            ts=datetime.utcnow())

        except Exception as e:
            logger.warning(f"snapshot save failed: {e}")

    def _save_event(self, run_id, ev):
        try:
            # [PHASE1 신규] 변경사항을 DATA/COPY/VISUAL 중 정확히 하나로 귀속
            ct = ev.change_type or ""
            field = ev.field_name or ""
            if ct == "visual" or field in ("screenshot", "image"):
                bucket = "VISUAL"
            elif ct in ("technical", "navigation") or field in ("schema_type", "dom", "canonical_url"):
                bucket = "DATA"
            else:
                bucket = "COPY"

            self._exec("""
                INSERT INTO detected_changes
                (crawl_run_id, url, change_type, change_category,
                 field_name, before_value, after_value,
                 severity, severity_level, severity_reason,
                 summary, char_added, char_removed,
                 diff_ratio, evidence, tier_level, analysis_bucket, detected_at)
                VALUES (:r,:u,:ct,:cc,:fn,:bv,:av,:sev,:lv,:sr,:sm,:ca,:cr,:dr,:evd,:tl,:bk,:ts)
            """,
            r=run_id, u=ev.url,
            ct=ev.change_type,
            cc=ev.severity_level,
            fn=ev.field_name,
            bv=ev.before_value,
            av=ev.after_value,
            sev=ev.severity_legacy,
            lv=ev.severity_level,
            sr=ev.summary,
            sm=ev.summary,
            ca=ev.char_added,
            cr=ev.char_removed,
            dr=ev.diff_ratio,
            evd=json.dumps(ev.evidence, ensure_ascii=False),
            tl=ev.tier_level,
            bk=bucket,
            ts=ev.detected_at)

        except Exception as e:
            logger.warning(f"event save failed: {e}")

    # ─────────────────────────────────────────────
    # DB
    # ─────────────────────────────────────────────
    def _exec(self, sql, **params):
        try:
            with self.sync_engine.connect() as conn:
                conn.execute(text(sql), params)
                conn.commit()
        except Exception as e:
            logger.warning(f"sql failed: {e}")

    def _load_db_urls(self, site_key: str) -> List[Dict]:
        """
        [FIX] SEED URL(config.py) + DB 등록 URL(monitored_urls 테이블) 머지.
        기존 코드는 DB만 조회해서 monitored_urls가 비어 있으면 0 URLs 반환했음.
        load_active_urls()가 시드 + DB를 중복 제거 후 합산해 반환.
        """
        try:
            with self.sync_engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT url FROM monitored_urls
                    WHERE enabled=true AND site_key=:s
                """), {"s": site_key}).fetchall()

            db_urls = [r[0] for r in rows]

        except Exception as e:
            logger.warning(f"monitored_urls query failed ({site_key}): {e} — seed only")
            db_urls = []

        # SEED_TARGETS의 seed_urls + DB 등록분 머지 (중복 제거, tier 자동 계산)
        return load_active_urls(site_key, db_urls if db_urls else None)
