import os
import smtplib
import ssl
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from sqlalchemy import text

LEVEL_KO = {"L5": "높음", "L4": "높음", "L3": "높음", "L2": "보통", "L1": "낮음", "L0": "낮음"}
LEVEL_COLOR = {"높음": "#FF3B30", "보통": "#FF9F0A", "낮음": "#34C759"}
SITE_KO = {"samsung": "Samsung", "apple": "Apple", "google_pixel": "Google Pixel", "xiaomi": "Xiaomi", "oppo": "OPPO", "vivo": "vivo", "sony_audio": "Sony Audio", "garmin": "Garmin", "dell": "Dell", "meta_ai_glasses": "Meta AI Glasses"}

# 점수 신호등 / 축 색 (PPTX·화면과 동일 기준)
TIER_COLOR = {"good": "#1F9E5C", "mid": "#E0A008", "bad": "#D8362F", "none": "#9AA0A8"}
TIER_LABEL = {"good": "Strong", "mid": "Moderate", "bad": "Needs Attention", "none": "근거 없음"}
AXIS_META = [("data", "DATA", "#0A66E0"), ("copy", "COPY", "#7A3EA1"), ("visual", "VISUAL", "#1A7F37")]


def _tier(score):
    if score is None:
        return "none"
    return "good" if score >= 70 else "mid" if score >= 40 else "bad"


# 이메일에서는 이 캐비엇 문구를 노출하지 않는다(액션 텍스트에서 제거).
_CAV = " (HTML 신호 기준, 실제 이미지 미검증)"


def _strip_cav(s):
    return (s or "").replace(_CAV, "")


def _kst(dt):
    if not dt:
        return ""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", ""))
        except Exception:
            return dt
    return (dt + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")


def _short(value, fallback="값 없음", limit=220):
    text_value = fallback if value is None or value == "" else str(value)
    text_value = text_value.replace("\r", " ").replace("\n", " ").strip()
    return escape(text_value[:limit])


class EmailService:
    def __init__(self, engine):
        self.engine = engine
        self.server = os.getenv("SMTP_SERVER", "smtp.naver.com")
        self.port = int(os.getenv("SMTP_PORT", "587"))
        self.sender = os.getenv("SENDER_EMAIL", "")
        self.password = os.getenv("SENDER_PASSWORD", "")
        self.recipient = os.getenv("RECIPIENT_EMAIL", "")
        self.enabled = os.getenv("EMAIL_REPORT_ENABLED", "true").lower() == "true"

    def configured(self):
        missing = []
        if not self.sender:
            missing.append("SENDER_EMAIL")
        if not self.password:
            missing.append("SENDER_PASSWORD")
        if not self.recipient:
            missing.append("RECIPIENT_EMAIL")
        return missing

    def _latest(self):
        with self.engine.connect() as conn:
            run = conn.execute(text("SELECT crawl_run_id, site_name, started_at, total_changes_detected FROM crawl_runs WHERE status='completed' ORDER BY started_at DESC LIMIT 1")).fetchone()
            if not run:
                return None, [], None, ""
            changes = conn.execute(text("SELECT url, site_key, severity_level, change_type, field_name, summary, before_value, after_value FROM detected_changes WHERE crawl_run_id=:run_id ORDER BY severity_level DESC, id DESC LIMIT 30"), {"run_id": run[0]}).fetchall()
            pov = conn.execute(text("SELECT observation, hypothesis FROM povs WHERE related_crawl_run_id=:run_id LIMIT 1"), {"run_id": run[0]}).fetchone()
        return run, changes, pov, _kst(run[2])

    def _report_data(self):
        """최신 세션 종합: 사이트별 축 점수/근거/액션(전 사이트), Samsung 3축 + 경쟁사 평균,
        제품군별 변경·커버리지 요약, 세션 요약, 세션 변경점(top 30)."""
        import json
        from export_service import _score_breakdown, _priority_action
        data = {"when": "", "sites": 0, "changes": 0, "axes": [], "summary": "",
                "rows": [], "sites_detail": [], "products": []}
        site_bd, site_facts, site_ins = {}, {}, {}
        prod_rows = []
        try:
            with self.engine.connect() as conn:
                runs = conn.execute(text(
                    "SELECT crawl_run_id, site_name, session_id, started_at, total_changes_detected "
                    "FROM crawl_runs WHERE status='completed' ORDER BY started_at DESC LIMIT 60")).fetchall()
                if not runs:
                    return data
                newest = runs[0]
                sess = newest[2]
                session_runs = [r for r in runs if sess and r[2] == sess] or [newest]
                data["when"] = _kst(newest[3])
                data["sites"] = len(session_runs)
                data["changes"] = sum((r[4] or 0) for r in session_runs)
                run_ids = [r[0] for r in session_runs]
                for r in session_runs:
                    prow = conn.execute(text(
                        "SELECT data_analysis, copy_analysis, visual_analysis FROM povs "
                        "WHERE related_crawl_run_id=:r LIMIT 1"), {"r": r[0]}).fetchone()
                    if not prow:
                        continue
                    for idx, (bucket, _l, _c) in enumerate(AXIS_META):
                        block = {}
                        if prow[idx]:
                            try:
                                block = json.loads(prow[idx]) or {}
                            except Exception:
                                block = {}
                        facts = block.get("facts") or {}
                        site_bd.setdefault(r[1], {})[bucket] = _score_breakdown(bucket, facts)
                        site_facts.setdefault(r[1], {})[bucket] = facts
                        pts = [i.get("point") for i in (block.get("insights") or [])
                               if isinstance(i, dict) and i.get("point")]
                        site_ins.setdefault(r[1], {})[bucket] = pts
                if run_ids:
                    keys = ",".join(":r%d" % i for i in range(len(run_ids)))
                    params = {("r%d" % i): rid for i, rid in enumerate(run_ids)}
                    data["rows"] = conn.execute(text(
                        "SELECT url, site_key, severity_level, change_type, field_name, summary, before_value, after_value "
                        "FROM detected_changes WHERE crawl_run_id IN (" + keys + ") "
                        "ORDER BY severity_level DESC, id DESC LIMIT 30"), params).fetchall()
                    prod_rows = conn.execute(text(
                        "SELECT url, site_key FROM detected_changes WHERE crawl_run_id IN (" + keys + ") LIMIT 2000"),
                        params).fetchall()
        except Exception:
            return data

        for bucket, label, color in AXIS_META:
            our_bd = (site_bd.get("samsung") or {}).get(bucket)
            our_total = our_bd.get("total") if our_bd else None
            peer_vals = [(site_bd[s].get(bucket) or {}).get("total") for s in site_bd if s != "samsung" and site_bd[s].get(bucket)]
            peer_vals = [v for v in peer_vals if isinstance(v, (int, float))]
            peer_avg = round(sum(peer_vals) / len(peer_vals)) if peer_vals else None
            delta = (our_total - peer_avg) if (our_total is not None and peer_avg is not None) else None
            facts = (site_facts.get("samsung") or {}).get(bucket) or {}
            data["axes"].append({
                "label": label, "color": color, "total": our_total, "tier": _tier(our_total),
                "peer_avg": peer_avg, "delta": delta,
                "action": _strip_cav(_priority_action(bucket, facts, our_bd or {"all": []})),
            })

        # 사이트별 상세(전 사이트): 점수 + 근거 + 우선 액션
        ordered = ([s for s in site_bd if s == "samsung"] +
                   [s for s in site_bd if s != "samsung"])
        for site in ordered:
            axes = []
            for bucket, label, color in AXIS_META:
                bd = site_bd[site].get(bucket)
                total = bd.get("total") if bd else None
                ev = (site_ins.get(site, {}).get(bucket) or [None])[0]
                facts = site_facts[site].get(bucket) or {}
                axes.append({
                    "label": label, "color": color, "total": total, "tier": _tier(total),
                    "evidence": ev, "action": _strip_cav(_priority_action(bucket, facts, bd or {"all": []})),
                })
            data["sites_detail"].append({
                "name": SITE_KO.get(site, site), "is_ours": site == "samsung", "axes": axes,
            })

        # 제품군별 변경·커버리지 요약
        try:
            from config import product_category_for_url, product_category_label
            pmap = {}
            for row in prod_rows:
                url = row[0] or ""
                cat = product_category_for_url(url)
                d = pmap.setdefault(cat, {"changes": 0, "sites": set()})
                d["changes"] += 1
                d["sites"].add(SITE_KO.get(row[1], row[1] or "미분류"))
            data["products"] = [
                {"label": product_category_label(cat), "changes": v["changes"],
                 "sites": sorted(v["sites"])}
                for cat, v in sorted(pmap.items(), key=lambda kv: -kv[1]["changes"])
            ]
        except Exception:
            data["products"] = []

        parts = ["이번 수집 %d개 사이트 · 변경 %d건." % (data["sites"], data["changes"])]
        if any(a["total"] is not None for a in data["axes"]):
            parts.append("Samsung 종합 " + " / ".join(
                "%s %s" % (a["label"], "-" if a["total"] is None else a["total"]) for a in data["axes"]) + ".")
            dparts = [a for a in data["axes"] if a["delta"] is not None]
            if dparts:
                parts.append("경쟁사 평균 대비 " + " / ".join(
                    "%s %s%d" % (a["label"], "+" if a["delta"] >= 0 else "", a["delta"]) for a in dparts) + ".")
        data["summary"] = " ".join(parts)
        return data

    def _sites_detail_html(self, sites_detail):
        """사이트별 현황: 각 사이트 3축 점수 + 근거 + 우선 액션(컴팩트 카드)."""
        if not sites_detail:
            return ""
        cards = ""
        for s in sites_detail:
            chips = ""
            lines = ""
            for a in s["axes"]:
                tc = TIER_COLOR[a["tier"]]
                score = "-" if a["total"] is None else str(a["total"])
                chips += (
                    "<td width='33%' valign='top' style='padding:3px'>"
                    "<div style='border:1px solid #EEF0F3;border-radius:8px;padding:7px 6px;text-align:center'>"
                    "<span style='font-size:10px;font-weight:700;color:" + a["color"] + "'>" + a["label"] + "</span>"
                    "<div style='font-size:18px;font-weight:800;color:" + tc + ";line-height:1.1'>" + score + "</div>"
                    "<span style='font-size:9.5px;color:#98A2B3'>" + TIER_LABEL[a["tier"]] + "</span>"
                    "</div></td>"
                )
                ev = _short(a.get("evidence") or "", "", 72) if a.get("evidence") else ""
                act = _short(a.get("action") or "", "", 96)
                detail = ev + (" · " if ev else "") + act
                lines += (
                    "<div style='font-size:11.5px;color:#475467;line-height:1.55;margin-top:3px'>"
                    "<span style='display:inline-block;width:7px;height:7px;border-radius:2px;background:"
                    + a["color"] + ";margin-right:6px'></span>"
                    "<b style='color:#101318'>" + a["label"] + "</b> " + detail + "</div>"
                )
            star = "★ " if s["is_ours"] else ""
            border = "#0A66E0" if s["is_ours"] else "#EAECF0"
            cards += (
                "<div style='border:1px solid " + border + ";border-radius:10px;padding:12px;margin-top:10px'>"
                "<div style='font-size:13px;font-weight:800;color:#101318;margin-bottom:6px'>" + star + escape(s["name"]) + "</div>"
                "<table role='presentation' width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse'><tr>" + chips + "</tr></table>"
                + lines +
                "</div>"
            )
        return ("<div style='font-size:13px;font-weight:700;color:#101318;margin:0 0 2px'>사이트별 현황 "
                "<span style='font-weight:400;color:#667085'>(점수 · 근거 · 우선 액션)</span></div>" + cards)

    def _products_html(self, products):
        """제품군별 변경·커버리지 요약."""
        if not products:
            return ""
        rows = ""
        for p in products:
            rows += (
                "<tr>"
                "<td style='padding:8px;border-top:1px solid #EAECF0;font-size:12.5px;font-weight:700;color:#101318;white-space:nowrap'>" + escape(p["label"]) + "</td>"
                "<td style='padding:8px;border-top:1px solid #EAECF0;font-size:12.5px;color:#344054'>변경 " + str(p["changes"]) + "건</td>"
                "<td style='padding:8px;border-top:1px solid #EAECF0;font-size:11.5px;color:#667085'>" + escape(", ".join(p["sites"])) + "</td>"
                "</tr>"
            )
        return (
            "<div style='font-size:13px;font-weight:700;color:#101318;margin:0 0 6px'>제품군별 요약</div>"
            "<table role='presentation' width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse'>"
            "<tr style='color:#667085;font-size:11px;text-align:left'><th style='padding:6px 8px'>제품군</th><th style='padding:6px 8px'>변경</th><th style='padding:6px 8px'>변경 감지 사이트</th></tr>"
            + rows + "</table>"
            "<div style='font-size:10.5px;color:#98A2B3;margin-top:6px'>제품군별 변경 건수·커버리지 기준. 축 점수는 사이트 단위와 동일 소스(제품군별 별도 점수는 아님).</div>"
        )

    def _scoreboard_html(self, axes):
        """우리 3축 점수 카드(가로 3칸, 경쟁사 평균 대비 포함) + 우선 액션 목록."""
        if not axes or not any(a["total"] is not None for a in axes):
            return ""
        cells = ""
        for a in axes:
            tc = TIER_COLOR[a["tier"]]
            score_txt = "-" if a["total"] is None else str(a["total"])
            if a["delta"] is None:
                delta_html = "<div style='font-size:10.5px;color:#98A2B3'>경쟁사 평균 —</div>"
            else:
                dcol = "#1F9E5C" if a["delta"] > 0 else ("#D8362F" if a["delta"] < 0 else "#98A2B3")
                arrow = "▲ +" if a["delta"] > 0 else ("▼ " if a["delta"] < 0 else "= ")
                pv = "-" if a["peer_avg"] is None else str(a["peer_avg"])
                delta_html = (
                    "<div style='font-size:10.5px;font-weight:700;color:" + dcol + "'>vs 경쟁사 " + arrow + str(abs(a["delta"])) + "p</div>"
                    "<div style='font-size:10px;color:#98A2B3'>경쟁사 평균 " + pv + "</div>")
            cells += (
                "<td width='33%' valign='top' style='padding:5px'>"
                "<div style='border:1px solid #EAECF0;border-radius:10px;padding:12px 8px;text-align:center'>"
                "<div style='font-size:11px;font-weight:700;color:" + a["color"] + "'>" + a["label"] + "</div>"
                "<div style='font-size:28px;font-weight:800;color:" + tc + ";line-height:1.2;margin:3px 0'>" + score_txt + "</div>"
                "<div style='font-size:11px;color:#667085;margin-bottom:5px'>" + TIER_LABEL[a["tier"]] + "</div>"
                + delta_html +
                "</div></td>"
            )
        actions = ""
        for a in axes:
            actions += (
                "<div style='font-size:12.5px;color:#344054;line-height:1.6;margin-top:6px'>"
                "<span style='display:inline-block;width:8px;height:8px;border-radius:2px;background:"
                + a["color"] + ";margin-right:7px'></span>"
                "<b style='color:#101318'>" + a["label"] + "</b> " + escape(a["action"]) + "</div>"
            )
        return (
            "<div style='font-size:13px;font-weight:700;color:#101318;margin:4px 0 6px'>우리 현황 (Samsung) · 종합 점수 <span style='font-weight:400;color:#667085'>(경쟁사 평균 대비)</span></div>"
            "<table role='presentation' width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse'><tr>" + cells + "</tr></table>"
            "<div style='font-size:12px;font-weight:700;color:#101318;margin:14px 0 2px'>우선 액션</div>"
            + actions +
            "<div style='font-size:10.5px;color:#98A2B3;margin-top:8px'>점수=각 축 하위지표 전체 평균 · 경쟁사 평균=비-Samsung 사이트 평균</div>"
        )

    def _row(self, change):
        level = LEVEL_KO.get(change[2], "낮음")
        color = LEVEL_COLOR[level]
        site = SITE_KO.get(change[1], change[1] or "미분류")
        summary = _short(change[5], "변경 요약 없음")
        before = _short(change[6], "이전 값 없음", 120)
        after = _short(change[7], "현재 값 없음", 120)
        url = _short(change[0], "URL 없음", 300)
        return ("<tr>" +
            "<td style='padding:10px 8px;border-top:1px solid #EAECF0;font-size:12px;white-space:nowrap'>" + escape(site) + "</td>" +
            "<td style='padding:10px 8px;border-top:1px solid #EAECF0'><span style='font-size:11px;font-weight:700;color:#fff;background:" + color + ";padding:3px 8px;border-radius:6px'>" + level + "</span></td>" +
            "<td style='padding:10px 8px;border-top:1px solid #EAECF0;font-size:13px;line-height:1.5'><b>" + summary + "</b>" +
            "<div style='color:#667085;margin-top:4px'>이전: " + before + "</div>" +
            "<div style='color:#344054'>현재: " + after + "</div>" +
            "<div style='font-family:monospace;color:#98A2B3;font-size:11px;margin-top:4px;word-break:break-all'>" + url + "</div></td></tr>")

    def build_html(self, report_type="morning"):
        d = self._report_data()
        when = d["when"]
        if not d["when"] and not d["axes"] and not d["rows"]:
            body = "<p style='color:#667085'>아직 수집 데이터가 없습니다.</p>"
        else:
            summary = escape(d["summary"] or "최근 모니터링 결과입니다.")
            scoreboard = self._scoreboard_html(d["axes"])
            sites_detail = self._sites_detail_html(d.get("sites_detail") or [])
            products = self._products_html(d.get("products") or [])
            rows = "".join(self._row(r) for r in d["rows"])
            if not rows:
                rows = "<tr><td colspan='3' style='padding:14px;color:#667085;border-top:1px solid #EAECF0'>이번 수집에서는 변경점이 없습니다. 페이지별 현재 상태를 확인해 주세요.</td></tr>"
            sep = "<div style='height:1px;background:#EAECF0;margin:18px 0'></div>"
            changes_section = (
                "<div style='font-size:13px;font-weight:700;color:#101318;margin:0 0 6px'>주요 변경점</div>"
                "<table style='width:100%;border-collapse:collapse'><tr style='color:#667085;font-size:11px;text-align:left'><th style='padding:6px 8px'>구분</th><th style='padding:6px 8px'>중요도</th><th style='padding:6px 8px'>변경 내용</th></tr>" + rows + "</table>"
            )
            body = (
                # 요약 (문장 + Samsung 스코어보드)
                "<p style='font-size:14px;color:#344054;line-height:1.7;margin:0 0 16px'>" + summary + "</p>"
                + (scoreboard + sep if scoreboard else "")
                # 변화
                + changes_section + sep
                # 사이트별
                + (sites_detail + sep if sites_detail else "")
                # 제품별
                + (products if products else "")
            )
        header_meta = "변경 " + str(d["changes"]) + "건" + (" · " + str(d["sites"]) + "개 사이트" if d["sites"] else "")
        return "<div style='max-width:720px;margin:0 auto;background:#F4F5F7;padding:20px;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif'><div style='background:#fff;border-radius:12px;padding:24px;border:1px solid #EAECF0'><div style='font-size:12px;color:#667085;font-weight:700'>애플스토커 사과 🍎</div><h1 style='font-size:22px;margin:6px 0 2px'>" + escape(when or datetime.now().strftime("%Y-%m-%d %H:%M")) + " KST</h1><div style='font-size:13px;color:#667085'>" + header_meta + "</div><div style='margin-top:16px'>" + body + "</div></div></div>"

    def send(self, report_type="morning"):
        if not self.enabled:
            return {"status": "skipped", "reason": "EMAIL_REPORT_ENABLED is false"}
        missing = self.configured()
        if missing:
            return {"status": "skipped", "reason": "missing email settings: " + ", ".join(missing)}
        msg = MIMEMultipart("alternative")
        try:
            _cnt = self._report_data().get("changes", 0)
        except Exception:
            _cnt = 0
        rt_ko = "조간" if report_type == "morning" else ("석간" if report_type == "evening" else report_type)
        msg["Subject"] = "[Apple Stalker] " + rt_ko + " 리포트 · " + datetime.now().strftime("%Y-%m-%d") + " · 변경 " + str(_cnt) + "건"
        msg["From"] = self.sender
        msg["To"] = self.recipient
        try:
            msg.attach(MIMEText(self.build_html(report_type), "html", "utf-8"))
            # [FIX] 타임아웃을 30s→10s로 줄임 — Render 게이트웨이가 먼저 타임아웃시켜
            # "빈 500"이 뜨는 것을 방지. SMTP가 진짜 안 되면 10초 안에 우리 코드가
            # 먼저 TimeoutError를 잡아 실제 원인을 응답한다.
            if self.port == 465:
                with smtplib.SMTP_SSL(self.server, self.port, context=ssl.create_default_context(), timeout=10) as smtp:
                    smtp.login(self.sender, self.password)
                    smtp.sendmail(self.sender, [self.recipient], msg.as_string())
            else:
                with smtplib.SMTP(self.server, self.port, timeout=10) as smtp:
                    smtp.ehlo()
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.ehlo()
                    smtp.login(self.sender, self.password)
                    smtp.sendmail(self.sender, [self.recipient], msg.as_string())
            return {"status": "sent", "recipient": self.recipient}
        except Exception as exc:
            return {"status": "error", "error": type(exc).__name__ + ": " + str(exc)}

