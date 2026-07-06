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

    def _our_analysis(self):
        """우리(Samsung) 최신 완료 run의 DATA/COPY/VISUAL 분석에서 점수·우선 액션 산출.
        점수/액션 로직은 export_service 와 동일 함수 재사용(중복 방지)."""
        import json
        from export_service import _score_breakdown, _priority_action
        try:
            with self.engine.connect() as conn:
                row = conn.execute(text(
                    "SELECT p.data_analysis, p.copy_analysis, p.visual_analysis "
                    "FROM povs p JOIN crawl_runs r ON p.related_crawl_run_id = r.crawl_run_id "
                    "WHERE r.site_name = 'samsung' AND r.status = 'completed' "
                    "ORDER BY r.started_at DESC LIMIT 1")).fetchone()
        except Exception:
            row = None
        if not row:
            return []
        out = []
        for idx, (bucket, label, color) in enumerate(AXIS_META):
            block = {}
            if row[idx]:
                try:
                    block = json.loads(row[idx]) or {}
                except Exception:
                    block = {}
            facts = block.get("facts") or {}
            bd = _score_breakdown(bucket, facts)
            total = bd.get("total")
            out.append({
                "label": label, "color": color, "total": total,
                "tier": _tier(total), "action": _priority_action(bucket, facts, bd),
            })
        return out

    def _scoreboard_html(self, analysis):
        """우리 3축 점수 카드(가로 3칸) + 우선 액션 목록."""
        if not analysis:
            return ""
        cells = ""
        for a in analysis:
            tc = TIER_COLOR[a["tier"]]
            score_txt = "-" if a["total"] is None else str(a["total"])
            cells += (
                "<td width='33%' valign='top' style='padding:5px'>"
                "<div style='border:1px solid #EAECF0;border-radius:10px;padding:12px 8px;text-align:center'>"
                "<div style='font-size:11px;font-weight:700;color:" + a["color"] + "'>" + a["label"] + "</div>"
                "<div style='font-size:28px;font-weight:800;color:" + tc + ";line-height:1.2;margin:3px 0'>" + score_txt + "</div>"
                "<div style='font-size:11px;color:#667085'>" + TIER_LABEL[a["tier"]] + "</div>"
                "</div></td>"
            )
        actions = ""
        for a in analysis:
            actions += (
                "<div style='font-size:12.5px;color:#344054;line-height:1.6;margin-top:6px'>"
                "<span style='display:inline-block;width:8px;height:8px;border-radius:2px;background:"
                + a["color"] + ";margin-right:7px'></span>"
                "<b style='color:#101318'>" + a["label"] + "</b> " + escape(a["action"]) + "</div>"
            )
        return (
            "<div style='font-size:13px;font-weight:700;color:#101318;margin:4px 0 6px'>우리 현황 (Samsung) · 종합 점수</div>"
            "<table role='presentation' width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse'><tr>" + cells + "</tr></table>"
            "<div style='font-size:12px;font-weight:700;color:#101318;margin:14px 0 2px'>우선 액션</div>"
            + actions +
            "<div style='font-size:10.5px;color:#98A2B3;margin-top:8px'>점수=각 축 하위지표 전체 평균 · VISUAL은 HTML 신호 기준(실제 이미지 미검증)</div>"
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
        run, changes, pov, when = self._latest()
        if not run:
            body = "<p style='color:#667085'>아직 수집 데이터가 없습니다.</p>"
            count = 0
        else:
            count = run[3] or 0
            summary = escape((pov[0] if pov else "") or "최근 모니터링 결과입니다.")
            scoreboard = self._scoreboard_html(self._our_analysis())
            rows = "".join(self._row(change) for change in changes)
            if not rows:
                rows = "<tr><td colspan='3' style='padding:14px;color:#667085;border-top:1px solid #EAECF0'>이번 수집에서는 변경점이 없습니다. 페이지별 현재 상태를 확인해 주세요.</td></tr>"
            body = (
                "<p style='font-size:14px;color:#344054;line-height:1.7;margin:0 0 16px'>" + summary + "</p>"
                + (scoreboard + "<div style='height:1px;background:#EAECF0;margin:18px 0'></div>" if scoreboard else "")
                + "<div style='font-size:13px;font-weight:700;color:#101318;margin:0 0 6px'>주요 변경점</div>"
                + "<table style='width:100%;border-collapse:collapse'><tr style='color:#667085;font-size:11px;text-align:left'><th style='padding:6px 8px'>구분</th><th style='padding:6px 8px'>중요도</th><th style='padding:6px 8px'>변경 내용</th></tr>" + rows + "</table>"
            )
        return "<div style='max-width:720px;margin:0 auto;background:#F4F5F7;padding:20px;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif'><div style='background:#fff;border-radius:12px;padding:24px;border:1px solid #EAECF0'><div style='font-size:12px;color:#667085;font-weight:700'>APPLE STALKER · " + escape(report_type) + " report</div><h1 style='font-size:22px;margin:6px 0 2px'>" + escape(when or datetime.now().strftime("%Y-%m-%d %H:%M")) + " KST</h1><div style='font-size:13px;color:#667085'>변경 " + str(count) + "건</div><div style='margin-top:16px'>" + body + "</div></div></div>"

    def send(self, report_type="morning"):
        if not self.enabled:
            return {"status": "skipped", "reason": "EMAIL_REPORT_ENABLED is false"}
        missing = self.configured()
        if missing:
            return {"status": "skipped", "reason": "missing email settings: " + ", ".join(missing)}
        msg = MIMEMultipart("alternative")
        try:
            _run = self._latest()[0]
            _cnt = (_run[3] or 0) if _run else 0
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

