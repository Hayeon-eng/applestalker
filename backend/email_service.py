"""
email_service.py — 일일 리포트 메일 (SMTP). 설정 없으면 조용히 skip.
"""
import os, smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from sqlalchemy import text


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
                return None, [], None
            ch = c.execute(text(
                "SELECT url, severity_level, change_type, summary FROM detected_changes "
                "WHERE crawl_run_id=:r ORDER BY severity_level DESC LIMIT 12"),
                {"r": run[0]}).fetchall()
            pov = c.execute(text(
                "SELECT observation, hypothesis FROM povs WHERE related_crawl_run_id=:r LIMIT 1"),
                {"r": run[0]}).fetchone()
        return run, ch, pov

    def build_html(self, report_type="morning") -> str:
        run, ch, pov = self._latest()
        when = datetime.now().strftime("%Y-%m-%d %H:%M")
        if not run:
            body = "<p>아직 크롤 데이터가 없습니다. 크롤을 먼저 실행하세요.</p>"
        else:
            rows = "".join(
                f'<tr><td style="padding:6px 0;font-family:monospace;font-size:11px;color:#8E8E93">{c[1]}</td>'
                f'<td style="padding:6px 8px;font-size:13px">{c[3] or ""}</td>'
                f'<td style="padding:6px 0;font-family:monospace;font-size:11px;color:#8E8E93">{c[0]}</td></tr>'
                for c in ch) or '<tr><td colspan="3" style="color:#8E8E93;padding:8px 0">오늘 변경 없음 — 현황 분석을 대시보드에서 확인하세요.</td></tr>'
            insight = (pov[0] if pov else "") or ""
            aeo = (pov[1] if pov else "") or ""
            body = (f'<p style="font-size:13px;color:#3A3A3C">{insight}</p>'
                    f'<p style="font-size:12px;color:#8E8E93">{aeo}</p>'
                    f'<table style="width:100%;border-collapse:collapse;margin-top:12px">{rows}</table>')
        return f"""<div style="max-width:640px;margin:0 auto;font-family:-apple-system,Arial,sans-serif">
          <div style="background:#fff;border-radius:16px;padding:22px;box-shadow:0 1px 4px rgba(0,0,0,.06)">
            <div style="font-size:12px;color:#8E8E93;font-weight:600">APPLE STALKER · {report_type} 리포트</div>
            <div style="font-size:20px;font-weight:700;margin-top:4px">{when} KST</div>
            <div style="font-size:12px;color:#8E8E93;margin-top:4px">변경 {run[3] if run else 0}건</div>
            <div style="margin-top:14px">{body}</div>
          </div></div>"""

    def send(self, report_type="morning") -> dict:
        if not self.enabled or not self.configured():
            return {"status": "skipped", "reason": "email not configured"}
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[Apple Stalker] {report_type} 리포트 {datetime.now():%Y-%m-%d}"
        msg["From"] = self.sender; msg["To"] = self.recipient
        msg.attach(MIMEText(self.build_html(report_type), "html"))
        try:
            with smtplib.SMTP(self.server, self.port) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(self.sender, self.password)
                s.sendmail(self.sender, [self.recipient], msg.as_string())
            return {"status": "sent", "recipient": self.recipient}
        except Exception as e:
            return {"status": "error", "error": str(e)}
