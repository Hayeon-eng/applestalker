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
SITE_KO = {"apple": "Apple 경쟁사", "samsung": "Samsung 당사"}


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
            rows = "".join(self._row(change) for change in changes)
            if not rows:
                rows = "<tr><td colspan='3' style='padding:14px;color:#667085;border-top:1px solid #EAECF0'>이번 수집에서는 변경점이 없습니다. 페이지별 현재 상태를 확인해 주세요.</td></tr>"
            body = "<p style='font-size:14px;color:#344054;line-height:1.7'>" + summary + "</p><table style='width:100%;border-collapse:collapse;margin-top:12px'><tr style='color:#667085;font-size:11px;text-align:left'><th style='padding:6px 8px'>구분</th><th style='padding:6px 8px'>중요도</th><th style='padding:6px 8px'>변경 내용</th></tr>" + rows + "</table>"
        return "<div style='max-width:720px;margin:0 auto;background:#F4F5F7;padding:20px;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif'><div style='background:#fff;border-radius:12px;padding:24px;border:1px solid #EAECF0'><div style='font-size:12px;color:#667085;font-weight:700'>APPLE STALKER · " + escape(report_type) + " report</div><h1 style='font-size:22px;margin:6px 0 2px'>" + escape(when or datetime.now().strftime("%Y-%m-%d %H:%M")) + " KST</h1><div style='font-size:13px;color:#667085'>변경 " + str(count) + "건</div><div style='margin-top:16px'>" + body + "</div></div></div>"

    def send(self, report_type="morning"):
        if not self.enabled:
            return {"status": "skipped", "reason": "EMAIL_REPORT_ENABLED is false"}
        missing = self.configured()
        if missing:
            return {"status": "skipped", "reason": "missing email settings: " + ", ".join(missing)}
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "[Apple Stalker] " + report_type + " report " + datetime.now().strftime("%Y-%m-%d")
        msg["From"] = self.sender
        msg["To"] = self.recipient
        try:
            msg.attach(MIMEText(self.build_html(report_type), "html", "utf-8"))
            if self.port == 465:
                with smtplib.SMTP_SSL(self.server, self.port, context=ssl.create_default_context(), timeout=30) as smtp:
                    smtp.login(self.sender, self.password)
                    smtp.sendmail(self.sender, [self.recipient], msg.as_string())
            else:
                with smtplib.SMTP(self.server, self.port, timeout=30) as smtp:
                    smtp.ehlo()
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.ehlo()
                    smtp.login(self.sender, self.password)
                    smtp.sendmail(self.sender, [self.recipient], msg.as_string())
            return {"status": "sent", "recipient": self.recipient}
        except Exception as exc:
            return {"status": "error", "error": type(exc).__name__ + ": " + str(exc)}

