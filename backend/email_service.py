"""
email_service.py — 일일 리포트 메일 (SMTP). 설정 없으면 조용히 skip.
내보내기(Excel/PPT)와 같은 톤: 텍스트 요약 + 변경 표(이전→현재), KST.
"""
import os, smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from sqlalchemy import text

LVKO = {"L5": "보통", "L4": "높음", "L3": "높음", "L2": "보통", "L1": "낮음", "L0": "낮음"}
LVC = {"높음": "#FF3B30", "보통": "#FF9F0A", "낮음": "#34C759"}
SITEKO = {"apple": "경쟁사·Apple", "samsung": "당사·Samsung"}
NONE_BEFORE = "(없음)"
NONE_AFTER = "(삭제)"


def _kst(dt):
    if not dt:
        return ""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", ""))
        except Exception:
            return dt
    return (dt + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")


class EmailService:
    def __init__(self, engine):
        self.engine = engine
        self.server = os.getenv("SMTP_SERVER", "smtp.naver.com")
        self.port = int(os.getenv("SMTP_PORT", "587"))
        self.sender = os.getenv("SENDER_EMAIL", "")
        self.password = os.getenv("SENDER_PASSWORD", "")
        self.recipient = os.getenv("RECIPIENT_EMAIL", "")
        self.enabled = os.getenv("EMAIL_REPORT_ENABLED", "true").lower() == "true"

    def configured(self) -> bool:
        return bool(self.sender and self.password and self.recipient)

    def _latest(self):
        with self.engine.connect() as c:
            run = c.execute(text(
                "SELECT crawl_run_id, site_name, started_at, total_changes_detected "
                "FROM crawl_runs WHERE status='completed' ORDER BY started_at DESC LIMIT 1")).fetchone()
            if not run:
                return None, [], None, ""
            ch = c.execute(text(
                "SELECT url, site_key, severity_level, change_type, field_name, summary, before_value, after_value "
                "FROM detected_changes WHERE crawl_run_id=:r ORDER BY severity_level DESC LIMIT 30"),
                {"r": run[0]}).fetchall()
            pov = c.execute(text(
                "SELECT observation, hypothesis FROM povs WHERE related_crawl_run_id=:r LIMIT 1"),
                {"r": run[0]}).fetchone()
        return run, ch, pov, _kst(run[2])

    def _row(self, c) -> str:
        site = SITEKO.get(c[1], c[1] or "")
        lv = LVKO.get(c[2], "낮음")
        before = (c[6] or NONE_BEFORE)[:60]
        after = (c[7] or NONE_AFTER)[:60]
        summary = c[5] or ""
        url = c[0] or ""
        badge = ("<span style='font-size:10px;font-weight:700;color:#fff;background:"
                 + LVC[lv] + ";padding:2px 7px;border-radius:6px'>" + lv + "</span>")
        change_line = "이전: " + before + " → 현재: " + after
        return (
            "<tr style='border-top:1px solid #E5E5EA'>"
            "<td style='padding:8px 6px;font-size:11px;white-space:nowrap'>" + site + "</td>"
            "<td style='padding:8px 6px'>" + badge + "</td>"
            "<td style='padding:8px 6px;font-size:12px'>" + summary +
            "<div style='font-family:monospace;font-size:10.5px;color:#8E8E93;margin-top:3px'>" + change_line + "</div>"
            "<div style='font-family:monospace;font-size:10px;color:#C7C7CC'>" + url + "</div></td></tr>")

    def build_html(self, report_type="morning") -> str:
        run, ch, pov, when = self._latest()
        if not run:
            body = "<p style='color:#8E8E93'>아직 크롤 데이터가 없습니다.</p>"
        else:
            summary = (pov[0] if pov else "") or "오늘의 변경점 요약입니다."
            rows = "".join(self._row(c) for c in ch)
            if not ch:
                rows = "<tr><td colspan='3' style='padding:10px;color:#8E8E93'>오늘 변경 없음 — 현행 유지</td></tr>"
            head = ("<tr style='color:#8E8E93;font-size:10px;text-align:left'>"
                    "<th style='padding:4px 6px'>대상</th>"
                    "<th style='padding:4px 6px'>중요도</th>"
                    "<th style='padding:4px 6px'>변경 내용 (이전→현재)</th></tr>")
            body = ("<p style='font-size:13px;color:#3A3A3C;line-height:1.6'>" + summary + "</p>"
                    "<table style='width:100%;border-collapse:collapse;margin-top:10px'>" + head + rows + "</table>")
        cnt = run[3] if run else 0
        return (
            "<div style=\"max-width:680px;margin:0 auto;font-family:-apple-system,Arial,sans-serif\">"
            "<div style=\"background:#fff;border-radius:16px;padding:22px;box-shadow:0 1px 4px rgba(0,0,0,.06)\">"
            "<div style=\"font-size:12px;color:#8E8E93;font-weight:600\">APPLE STALKER · " + report_type + " 리포트</div>"
            "<div style=\"font-size:20px;font-weight:700;margin-top:4px\">" + when + " KST</div>"
            "<div style=\"font-size:12px;color:#8E8E93;margin-top:4px\">변경 " + str(cnt) + "건</div>"
            "<div style=\"margin-top:14px\">" + body + "</div>"
            "</div></div>")

    def send(self, report_type="morning") -> dict:
        if not self.enabled or not self.configured():
            return {"status": "skipped", "reason": "email not configured"}
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "[Apple Stalker] " + report_type + " 리포트 " + datetime.now().strftime("%Y-%m-%d")
        msg["From"] = self.sender
        msg["To"] = self.recipient
        msg.attach(MIMEText(self.build_html(report_type), "html"))
        try:
            with smtplib.SMTP(self.server, self.port) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(self.sender, self.password)
                s.sendmail(self.sender, [self.recipient], msg.as_string())
            return {"status": "sent", "recipient": self.recipient}
        except Exception as e:
            return {"status": "error", "error": str(e)}
