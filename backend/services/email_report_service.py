"""
Email Report Service
Sends daily dashboard reports via email (twice daily at 09:00 and 14:00 KST).
"""

import os
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any, Optional
from pathlib import Path

from sqlalchemy import select, desc, func

from database.database import SessionLocal
from database.models import CrawlRun, DetectedChange, SamsungPOV, GEOSignal, TrendData
from loguru import logger


class EmailReportService:
    """
    Sends email reports with dashboard summary.
    Configured to send twice daily at 09:00 and 14:00 KST.
    """

    def __init__(
        self,
        smtp_server: str = None,
        smtp_port: int = None,
        sender_email: str = None,
        sender_password: str = None,
        recipient_email: str = None,
    ):
        self.smtp_server = smtp_server or os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
        self.sender_email = sender_email or os.getenv("SENDER_EMAIL", "")
        self.sender_password = sender_password or os.getenv("SENDER_PASSWORD", "")
        self.recipient_email = recipient_email or os.getenv(
            "RECIPIENT_EMAIL", "hayeon2.kwon@samsung.com"
        )
        self.is_configured = bool(
            self.sender_email and self.sender_password and self.recipient_email
        )

    def send_daily_report(self, report_type: str = "morning") -> Dict[str, Any]:
        """
        Send daily dashboard report via email.

        Args:
            report_type: 'morning' (09:00) or 'afternoon' (14:00)

        Returns:
            Send result
        """
        if not self.is_configured:
            logger.warning("Email not configured - skipping report")
            return {"status": "skipped", "reason": "Email not configured"}

        try:
            # Gather report data
            report_data = self._gather_report_data(report_type)

            # Generate HTML report
            html_content = self._generate_html_report(report_data, report_type)

            # Send email
            self._send_email(
                subject=f"[Apple Tracker] {report_type.capitalize()} Report - {datetime.now().strftime('%Y-%m-%d')}",
                html_content=html_content,
            )

            logger.info(f"Daily {report_type} report sent successfully")

            return {
                "status": "sent",
                "report_type": report_type,
                "recipient": self.recipient_email,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to send email report: {e}")
            return {
                "status": "failed",
                "error": str(e),
            }

    def _gather_report_data(self, report_type: str) -> Dict[str, Any]:
        """Gather all data for the report"""
        db = SessionLocal()

        try:
            now = datetime.utcnow()

            # Determine time range based on report type
            if report_type == "morning":
                # Changes since yesterday 14:00 KST (05:00 UTC)
                start_time = now - timedelta(days=1)
                start_time = start_time.replace(hour=5, minute=0, second=0, microsecond=0)
            else:  # afternoon
                # Changes since today 09:00 KST (00:00 UTC)
                start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)

            # Recent crawls
            crawls_query = (
                select(CrawlRun)
                .where(CrawlRun.started_at >= start_time)
                .order_by(desc(CrawlRun.started_at))
                .limit(10)
            )
            crawls = db.execute(crawls_query).scalars().all()

            # Changes summary
            changes_query = (
                select(DetectedChange)
                .where(DetectedChange.detected_at >= start_time)
                .order_by(desc(DetectedChange.detected_at))
                .limit(50)
            )
            changes = db.execute(changes_query).scalars().all()

            # Changes by severity
            severity_counts = {}
            for change in changes:
                severity_counts[change.severity] = severity_counts.get(change.severity, 0) + 1

            # Changes by type
            type_counts = {}
            for change in changes:
                type_counts[change.change_type] = type_counts.get(change.change_type, 0) + 1

            # Recent POVs
            povs_query = (
                select(SamsungPOV)
                .where(SamsungPOV.created_at >= start_time)
                .order_by(desc(SamsungPOV.created_at))
                .limit(20)
            )
            povs = db.execute(povs_query).scalars().all()

            # Priority POVs
            priority_povs = [p for p in povs if p.priority in ["critical", "high"]]

            # GEO Signals
            geo_query = (
                select(GEOSignal)
                .where(GEOSignal.detected_at >= start_time)
                .order_by(desc(GEOSignal.detected_at))
                .limit(30)
            )
            geo_signals = db.execute(geo_query).scalars().all()

            # Trend data (last 7 days)
            trend_start = now - timedelta(days=7)
            trends_query = select(TrendData).where(TrendData.recorded_at >= trend_start)
            trends = db.execute(trends_query).scalars().all()

            # Aggregate trends by type and site
            trend_summary = {}
            for trend in trends:
                key = f"{trend.site_name}_{trend.metric_type}"
                if key not in trend_summary:
                    trend_summary[key] = []
                trend_summary[key].append({
                    "value": trend.value,
                    "recorded_at": trend.recorded_at,
                })

            return {
                "report_period": {
                    "start": start_time.isoformat(),
                    "end": now.isoformat(),
                    "type": report_type,
                },
                "crawls": crawls,
                "changes": changes,
                "changes_by_severity": severity_counts,
                "changes_by_type": type_counts,
                "povs": povs,
                "priority_povs": priority_povs,
                "geo_signals": geo_signals,
                "trends": trend_summary,
                "summary": {
                    "total_crawls": len(crawls),
                    "total_changes": len(changes),
                    "critical_changes": severity_counts.get("critical", 0),
                    "high_changes": severity_counts.get("high", 0),
                    "total_povs": len(povs),
                    "priority_povs": len(priority_povs),
                    "geo_signals": len(geo_signals),
                },
            }

        finally:
            db.close()

    def _generate_html_report(self, data: Dict[str, Any], report_type: str) -> str:
        """Generate HTML email report"""
        summary = data["summary"]
        date_str = datetime.now().strftime("%Y년 %m월 %d일")
        time_str = "오전 9 시" if report_type == "morning" else "오후 2 시"

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #1d1d1f;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f7;
        }}
        .container {{
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .header {{
            border-bottom: 2px solid #005ce2;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            color: #005ce2;
            margin: 0;
            font-size: 24px;
        }}
        .header p {{
            color: #86868b;
            margin: 5px 0 0 0;
            font-size: 14px;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}
        .summary-card {{
            background: #f5f5f7;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }}
        .summary-card .value {{
            font-size: 28px;
            font-weight: bold;
            color: #005ce2;
        }}
        .summary-card .label {{
            font-size: 12px;
            color: #86868b;
            margin-top: 5px;
        }}
        .section {{
            margin-bottom: 30px;
        }}
        .section h2 {{
            font-size: 18px;
            color: #1d1d1f;
            border-left: 4px solid #005ce2;
            padding-left: 12px;
            margin-bottom: 15px;
        }}
        .change-item {{
            background: #fafafa;
            border-radius: 6px;
            padding: 12px;
            margin-bottom: 10px;
            border-left: 3px solid;
        }}
        .change-item.critical {{ border-left-color: #dc3545; }}
        .change-item.high {{ border-left-color: #fd7e14; }}
        .change-item.medium {{ border-left-color: #ffc107; }}
        .change-item.low {{ border-left-color: #28a745; }}
        .change-item .type {{
            font-weight: bold;
            font-size: 14px;
        }}
        .change-item .detail {{
            font-size: 13px;
            color: #666;
            margin-top: 5px;
        }}
        .pov-item {{
            background: #fff8e1;
            border-radius: 6px;
            padding: 12px;
            margin-bottom: 10px;
        }}
        .pov-item .observation {{
            font-weight: bold;
            font-size: 14px;
            margin-bottom: 8px;
        }}
        .pov-item .action {{
            font-size: 13px;
            color: #333;
        }}
        .pov-item.priority-critical {{
            background: #ffebee;
        }}
        .pov-item.priority-high {{
            background: #fff3e0;
        }}
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
            text-transform: uppercase;
        }}
        .badge-critical {{ background: #dc3545; color: white; }}
        .badge-high {{ background: #fd7e14; color: white; }}
        .badge-medium {{ background: #ffc107; color: #333; }}
        .badge-low {{ background: #28a745; color: white; }}
        .no-data {{
            text-align: center;
            color: #86868b;
            padding: 20px;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
            text-align: center;
            font-size: 12px;
            color: #86868b;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        th, td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
        }}
        th {{
            background: #f5f5f7;
            font-size: 12px;
            text-transform: uppercase;
            color: #86868b;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🍎 Apple Tracker Dashboard Report</h1>
            <p>{date_str} {time_str} 리포트 | Apple.com vs Samsung.com/sg 경쟁 분석</p>
        </div>

        <!-- Summary Grid -->
        <div class="summary-grid">
            <div class="summary-card">
                <div class="value">{summary['total_crawls']}</div>
                <div class="label">크롤 실행</div>
            </div>
            <div class="summary-card">
                <div class="value">{summary['total_changes']}</div>
                <div class="label">변화 감지</div>
            </div>
            <div class="summary-card">
                <div class="value">{summary['critical_changes'] + summary['high_changes']}</div>
                <div class="label">중요 변화</div>
            </div>
            <div class="summary-card">
                <div class="value">{summary['priority_povs']}</div>
                <div class="label">우선 POV</div>
            </div>
            <div class="summary-card">
                <div class="value">{summary['geo_signals']}</div>
                <div class="label">GEO 신호</div>
            </div>
        </div>

        <!-- Critical Changes -->
        <div class="section">
            <h2>🚨 중요 변화 (Critical/High)</h2>
            {self._render_changes(data['changes'], ['critical', 'high'])}
        </div>

        <!-- Samsung POVs -->
        <div class="section">
            <h2>💡 Samsung POV 추천</h2>
            {self._render_povs(data['priority_povs'])}
        </div>

        <!-- Changes by Type -->
        <div class="section">
            <h2>📊 변화 유형별 통계</h2>
            {self._render_change_types(data['changes_by_type'])}
        </div>

        <!-- GEO Signals -->
        <div class="section">
            <h2>🔍 GEO/AEO 신호</h2>
            {self._render_geo_signals(data['geo_signals'])}
        </div>

        <!-- Recent Crawls -->
        <div class="section">
            <h2>📈 최근 크롤 이력</h2>
            {self._render_crawls(data['crawls'])}
        </div>

        <div class="footer">
            <p>Apple Tracker - Competitive Intelligence Platform</p>
            <p>이 레포트는 매일 09:00, 14:00 에 자동 발송됩니다.</p>
        </div>
    </div>
</body>
</html>
        """
        return html

    def _render_changes(self, changes: List, severities: List[str]) -> str:
        """Render changes section"""
        filtered = [c for c in changes if c.severity in severities][:10]

        if not filtered:
            return '<div class="no-data">중요 변화가 없습니다.</div>'

        html = ""
        for change in filtered:
            html += f"""
            <div class="change-item {change.severity}">
                <div class="type">
                    <span class="badge badge-{change.severity}">{change.severity}</span>
                    {change.change_type} - {change.change_category}
                </div>
                <div class="detail">
                    URL: {change.url[:60]}...<br>
                    {change.severity_reason or change.field_name or ''}
                </div>
            </div>
            """
        return html

    def _render_povs(self, povs: List) -> str:
        """Render POVs section"""
        if not povs:
            return '<div class="no-data">POV 추천사항이 없습니다.</div>'

        html = ""
        for pov in povs[:10]:
            html += f"""
            <div class="pov-item priority-{pov.priority}">
                <div class="observation">
                    <span class="badge badge-{pov.priority}">{pov.priority}</span>
                    {pov.observation[:100]}...
                </div>
                <div class="action">
                    <strong>추천 액션:</strong> {pov.recommended_action[:150]}...
                </div>
            </div>
            """
        return html

    def _render_change_types(self, type_counts: Dict[str, int]) -> str:
        """Render change types table"""
        if not type_counts:
            return '<div class="no-data">데이터가 없습니다.</div>'

        html = """
        <table>
            <tr><th>유형</th><th>건수</th></tr>
        """
        for change_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            html += f"<tr><td>{change_type}</td><td>{count}</td></tr>"
        html += "</table>"
        return html

    def _render_geo_signals(self, signals: List) -> str:
        """Render GEO signals section"""
        if not signals:
            return '<div class="no-data">GEO 신호가 없습니다.</div>'

        signal_types = {}
        for s in signals:
            signal_types[s.signal_type] = signal_types.get(s.signal_type, 0) + 1

        html = """
        <table>
            <tr><th>신호 유형</th><th>건수</th><th>평균 강도</th></tr>
        """
        for signal_type, count in sorted(signal_types.items(), key=lambda x: x[1], reverse=True)[:10]:
            html += f"<tr><td>{signal_type}</td><td>{count}</td><td>-</td></tr>"
        html += "</table>"
        return html

    def _render_crawls(self, crawls: List) -> str:
        """Render crawls table"""
        if not crawls:
            return '<div class="no-data">크롤 이력이 없습니다.</div>'

        html = """
        <table>
            <tr><th>사이트</th><th>시작시간</th><th>상태</th><th>URL</th><th>변화</th></tr>
        """
        for crawl in crawls[:10]:
            time_str = crawl.started_at.strftime("%m/%d %H:%M") if crawl.started_at else "-"
            html += f"""
            <tr>
                <td>{crawl.site_name}</td>
                <td>{time_str}</td>
                <td>{crawl.status}</td>
                <td>{crawl.total_urls_crawled or 0}</td>
                <td>{crawl.total_changes_detected or 0}</td>
            </tr>
            """
        html += "</table>"
        return html

    def _send_email(self, subject: str, html_content: str):
        """Send email via SMTP"""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.sender_email
        msg["To"] = self.recipient_email

        # Attach HTML content
        msg.attach(MIMEText(html_content, "html"))

        # Send via SMTP
        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            server.sendmail(self.sender_email, self.recipient_email, msg.as_string())

    def send_test_email(self) -> Dict[str, Any]:
        """Send a test email"""
        if not self.is_configured:
            return {"status": "skipped", "reason": "Email not configured"}

        try:
            html_content = """
            <html>
            <body>
                <h1>🍎 Apple Tracker Test Email</h1>
                <p>이메일 설정이 정상적으로 작동합니다.</p>
                <p>매일 09:00, 14:00 에 대시보드 레포트가 발송됩니다.</p>
            </body>
            </html>
            """
            self._send_email(
                subject="[Apple Tracker] Test Email - 설정 확인",
                html_content=html_content,
            )
            return {"status": "sent", "message": "Test email sent successfully"}
        except Exception as e:
            return {"status": "failed", "error": str(e)}


# Global email service instance
email_service = EmailReportService()


def get_email_service() -> EmailReportService:
    """Get the email service instance"""
    return email_service


def send_morning_report():
    """Wrapper for scheduler - morning report"""
    service = get_email_service()
    return service.send_daily_report("morning")


def send_afternoon_report():
    """Wrapper for scheduler - afternoon report"""
    service = get_email_service()
    return service.send_daily_report("afternoon")
