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
        from datetime import timedelta, datetime as _dt
        def _kst(dt):
            if not dt: return ""
            if isinstance(dt, str):
                try: dt = _dt.fromisoformat(dt.replace("Z",""))
                except Exception: return dt
            return (dt + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")
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

    def build_html(self, report_type="morning") -> str:
        run, ch, pov, when = self._latest()
        LVKO = {"L5":"\ubcf4\ud1b5","L4":"\ub192\uc74c","L3":"\ub192\uc74c","L2":"\ubcf4\ud1b5","L1":"\ub0ae\uc74c","L0":"\ub0ae\uc74c"}
        LVC = {"\ub192\uc74c":"#FF3B30","\ubcf4\ud1b5":"#FF9F0A","\ub0ae\uc74c":"#34C759"}
        SITEKO = {"apple":"\uacbd\uc7c1\uc0ac·Apple","samsung":"\ub2f9\uc0ac·Samsung"}
        if not run:
            body = "<p style='color:#8E8E93'>\uc544\uc9c1 \ud06c\ub864 \ub370\uc774\ud130\uac00 \uc5c6\uc2b5\ub2c8\ub2e4.</p>"
        else:
            summary = (pov[0] if pov else "") or "\uc624\ub298\uc758 \ubcc0\uacbd\uc810 \uc694\uc57d\uc785\ub2c8\ub2e4."
            rows = ""
            for c in ch:
                site = SITEKO.get(c[1], c[1] or "")
                lv = LVKO.get(c[2], "\ub0ae\uc74c")
                rows += ("<tr style='border-top:1px solid #E5E5EA'>"
                    f"<td style='padding:8px 6px;font-size:11px;white-space:nowrap'>{site}</td>"
                    f"<td style='padding:8px 6px'><span style='font-size:10px;font-weight:700;color:#fff;background:{LVC[lv]};padding:2px 7px;border-radius:6px'>{lv}</span></td>"
                    f"<td style='padding:8px 6px;font-size:12px'>{c[5] or ''}"
                    f"<div style='font-family:monospace;font-size:10.5px;color:#8E8E93;margin-top:3px'>\uc774\uc804: {(c[6] or '(\uc5c6\uc74c)')[:60]} → \ud604\uc7ac: {(c[7] or '(\uc0ad\uc81c)')[:60]}</div>"
                    f"<div style='font-family:monospace;font-size:10px;color:#C7C7CC'>{c[0]}</div></td></tr>")
            if not ch:
                rows = "<tr><td colspan='3' style='padding:10px;color:#8E8E93'>\uc624\ub298 \ubcc0\uacbd \uc5c6\uc74c — \ud604\ud589 \uc720\uc9c0</td></tr>"
            body = (f"<p style='font-size:13px;color:#3A3A3C;line-height:1.6'>{summary}</p>"
                "<table style='width:100%;border-collapse:collapse;margin-top:10px'>"
                "<tr style='color:#8E8E93;font-size:10px;text-align:left'>"
                "<th style='padding:4px 6px'>\ub300\uc0c1</th><th style='padding:4px 6px'>\uc911\uc694\ub3c4</th><th style='padding:4px 6px'>\ubcc0\uacbd \ub0b4\uc6a9 (\uc774\uc804→\ud604\uc7ac)</th></tr>"
                f"{rows}</table>")
        return f"""<div style="max-width:680px;margin:0 auto;font-family:-apple-system,Arial,sans-serif">
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
