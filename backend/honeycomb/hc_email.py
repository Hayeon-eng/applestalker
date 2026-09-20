"""
hc_email.py — honeyComb 이메일 리포트 [2026-09 신규]

  build_html(run, prev_run=None)  → 메일 본문(HTML). "메일 복사" 버튼과 자동발송이 공유.
  send_email(run, prev_run=None)  → SMTP 발송. 환경변수는 email_service.py(애플스토커)와
                                     동일한 이름을 그대로 쓴다 — 같은 발신 계정을 도구별로
                                     따로 설정할 필요 없게.

큐비(qa_report.py)와 같은 톤(사이트/제품 카드 + 색상 배지)으로 맞췄다 — 도구마다 메일 느낌이
다르면 받는 사람 입장에서 매번 새로 읽어야 해서, 레이아웃 언어를 통일한다.
"""
from __future__ import annotations
import os
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from typing import Any, Dict, List, Optional

import hc_engine

STATUS_KO = {"top1": "1위", "topn": "상단 노출", "low": "하위 노출", "absent": "노출 없음",
             "unranked": "순위 밖", "unchecked": "미확인", "error": "오류"}
STATUS_COLOR = {"top1": "#1F9E5C", "topn": "#0A66E0", "low": "#E0A008", "absent": "#D8362F",
                "unranked": "#98A2B3", "unchecked": "#98A2B3", "error": "#D8362F"}


def _pct_bar(label: str, value: Optional[float], color: str) -> str:
    if value is None:
        return ""
    return ("<div style='margin-top:6px'>"
            "<div style='display:flex;justify-content:space-between;font-size:11.5px;color:#475467'>"
            "<span>" + escape(label) + "</span><span style='font-weight:700;color:" + color + "'>" + str(value) + "%</span></div>"
            "<div style='height:6px;background:#EEF0F3;border-radius:3px;margin-top:2px'>"
            "<div style='height:6px;width:" + str(min(100, value)) + "%;background:" + color + ";border-radius:3px'></div></div></div>")


def _status_table(by_status: Dict[str, int], total: int) -> str:
    cells = "".join(
        "<td style='text-align:center;padding:8px 4px'>"
        "<div style='font-size:18px;font-weight:800;color:" + STATUS_COLOR.get(s, "#344054") + "'>" + str(by_status.get(s, 0)) + "</div>"
        "<div style='font-size:10.5px;color:#667085;margin-top:2px'>" + STATUS_KO.get(s, s) + "</div></td>"
        for s in ("top1", "topn", "low", "absent", "unranked"))
    return "<table style='width:100%;border-collapse:collapse;margin-top:8px'><tr>" + cells + "</tr></table>"


def _changes_block(changes: List[Dict[str, Any]], cname: Dict[str, str], label: Dict[str, str]) -> str:
    if not changes:
        return ""
    rows = ""
    for ch in changes[:20]:
        parts = []
        c = ch["changes"]
        if "status" in c:
            a, b = c["status"]
            arrow_color = STATUS_COLOR.get(b, "#344054")
            parts.append("순위 상태 " + STATUS_KO.get(a, a) + " → <b style='color:" + arrow_color + "'>" + STATUS_KO.get(b, b) + "</b>")
        if "position" in c:
            a, b = c["position"]
            parts.append(f"순위 {a if a is not None else '—'} → <b>{b if b is not None else '—'}</b>")
        if "attrs" in c:
            g, l = c["attrs"]["gained"], c["attrs"]["lost"]
            if g:
                parts.append(f"<span style='color:#1F9E5C'>+속성 {len(g)}개 신규 노출</span>")
            if l:
                parts.append(f"<span style='color:#D8362F'>-속성 {len(l)}개 노출 중단</span>")
        rows += ("<div style='font-size:12px;padding:6px 0;border-bottom:1px solid #F2F4F7'>"
                 "<b>" + escape(cname.get(ch["country"], ch["country"])) + " · " + escape(label.get(ch["product"], ch["product"])) + "</b>"
                 " <span style='color:#667085'>" + escape(ch["keyword"]) + "</span>"
                 "<div style='color:#475467;margin-top:2px'>" + " · ".join(parts) + "</div></div>")
    more = f"<div style='font-size:11px;color:#98A2B3;margin-top:4px'>외 {len(changes) - 20}건 더</div>" if len(changes) > 20 else ""
    return ("<div style='margin-top:16px'>"
            "<div style='font-size:13px;font-weight:800;color:#101318;border-bottom:2px solid #8A5A00;padding-bottom:4px'>지난주 대비 변화 " + str(len(changes)) + "건</div>"
            + rows + more + "</div>")


def build_html(run: Dict[str, Any], prev_run: Optional[Dict[str, Any]] = None, config: Optional[Dict[str, Any]] = None) -> str:
    s = hc_engine.summarize(run, keyword_type="brand")
    cname = {c["code"]: c["label"] for c in (config or {}).get("countries", [])}
    plabel = {p["slug"]: p["label"] for p in (config or {}).get("products", [])}
    total = s["cells"]

    per_product_html = ""
    for slug, by in s.get("per_product", {}).items():
        chk = sum(by.get(x, 0) for x in ("top1", "topn", "low", "absent"))
        per_product_html += ("<div style='border:1px solid #EAECF0;border-radius:10px;padding:10px 12px;margin-top:8px'>"
                              "<div style='font-size:12.5px;font-weight:800;color:#101318'>" + escape(plabel.get(slug, slug)) + "</div>"
                              + _status_table(by, chk) + "</div>")

    stores_html = ""
    if s.get("first_stores"):
        top_stores = list(s["first_stores"].items())[:6]
        stores_html = ("<div style='margin-top:16px'>"
                        "<div style='font-size:13px;font-weight:800;color:#101318;border-bottom:2px solid #8A5A00;padding-bottom:4px'>1위 판매처 분포</div>"
                        "<div style='display:flex;flex-wrap:wrap;gap:6px;margin-top:8px'>"
                        + "".join(f"<span style='font-size:11.5px;background:#FFF7E6;border:1px solid #FCE3A6;border-radius:6px;padding:3px 9px'><b>{escape(store)}</b> {n}건</span>" for store, n in top_stores)
                        + "</div></div>")

    changes_html = ""
    if prev_run:
        changes_html = _changes_block(hc_engine.diff_runs(prev_run, run), cname, plabel)

    return (
        "<div style='max-width:720px;margin:0 auto;background:#F4F5F7;padding:20px;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif'>"
        "<div style='background:#fff;border-radius:12px;padding:24px;border:1px solid #EAECF0'>"
        "<div style='font-size:12px;color:#667085;font-weight:700'>허니콤 🍯🐝 — Google Shopping 노출 리포트</div>"
        "<h1 style='font-size:22px;margin:6px 0 2px'>" + escape(run.get("week") or run.get("at", "")) + "</h1>"
        "<div style='font-size:13px;color:#667085'>검사 " + str(total) + "건"
        + (f" · 1위 노출 {s['top1_rate']}%" if s.get("top1_rate") is not None else "")
        + (f" · 상단 노출(1~topN) {s['topn_rate']}%" if s.get("topn_rate") is not None else "")
        + (f" · 속성 노출률 {s['attr_entered_rate']}%" if s.get("attr_entered_rate") is not None else "")
        + "</div>"
        "<div style='margin-top:14px'>" + _status_table(s["by_status"], total) + "</div>"
        "<div style='margin-top:16px'>"
        "<div style='font-size:13px;font-weight:800;color:#101318;border-bottom:2px solid #8A5A00;padding-bottom:4px'>제품별 현황</div>"
        + per_product_html + "</div>"
        + stores_html + changes_html
        + "</div></div>")


def _smtp_send(subject: str, html: str) -> Dict[str, Any]:
    """[2026-09 신규] email_service.py(애플스토커)와 동일한 환경변수·발송 로직 — 도구별로 SMTP 설정을
    따로 두지 않고 같은 발신 계정을 공유한다. Render 타임아웃 전에 우리 코드가 먼저 실패 원인을 잡도록
    10초 제한도 그대로 맞춤."""
    server = os.getenv("SMTP_SERVER", "smtp.naver.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    sender = os.getenv("SENDER_EMAIL", "")
    password = os.getenv("SENDER_PASSWORD", "")
    recipient = os.getenv("HC_RECIPIENT_EMAIL") or os.getenv("RECIPIENT_EMAIL", "")
    if os.getenv("EMAIL_REPORT_ENABLED", "true").lower() != "true":
        return {"status": "skipped", "reason": "EMAIL_REPORT_ENABLED is false"}
    missing = [n for n, v in (("SENDER_EMAIL", sender), ("SENDER_PASSWORD", password), ("RECIPIENT_EMAIL", recipient)) if not v]
    if missing:
        return {"status": "skipped", "reason": "missing email settings: " + ", ".join(missing)}
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject; msg["From"] = sender; msg["To"] = recipient
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        if port == 465:
            with smtplib.SMTP_SSL(server, port, context=ssl.create_default_context(), timeout=10) as smtp:
                smtp.login(sender, password); smtp.sendmail(sender, [recipient], msg.as_string())
        else:
            with smtplib.SMTP(server, port, timeout=10) as smtp:
                smtp.ehlo(); smtp.starttls(context=ssl.create_default_context()); smtp.ehlo()
                smtp.login(sender, password); smtp.sendmail(sender, [recipient], msg.as_string())
        return {"status": "sent", "recipient": recipient}
    except Exception as exc:
        return {"status": "error", "error": type(exc).__name__ + ": " + str(exc)}


def send_email(run: Dict[str, Any], prev_run: Optional[Dict[str, Any]] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    s = hc_engine.summarize(run, keyword_type="brand")
    subject = f"[허니콤] Google Shopping 리포트 · {run.get('week') or run.get('at', '')} · 1위 {s.get('top1_rate', '—')}%"
    return _smtp_send(subject, build_html(run, prev_run, config))
