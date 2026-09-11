"""
launcher.py — ABC Tool 데스크톱 런처 [2026-09]

exe(PyInstaller) 진입점. Render 없이 PC 에서 A(Apple Stalker)·B(QA Bee)·C(honeyComb)가 동작하게 한다.
  1) config.json(exe 옆) → 환경변수(비밀번호·Gemini·SMTP·DB) 로 주입. 없으면 예시를 만들어 준다.
  2) Windows 시스템 프록시(레지스트리) → HTTP(S)_PROXY 로 주입(사내망). 없으면 직접 연결.
  3) DB: config 에 database_url 이 없으면 %APPDATA%\\ABCTool\\abc_tool.db (sqlite) — 재설치/업데이트에도 이력 유지.
  4) FastAPI(backend.main.app) + 정적 프론트(frontend_out) + 비밀번호 게이트(Next middleware 대체) + 설정 API/페이지
  5) 주간 자동 실행(스케줄러 스레드): config.schedule.mode == "auto" 일 때 지정 요일·시각에 크롤 → (옵션) 메일 자동 발송
  6) uvicorn 기동 후 기본 브라우저를 http://127.0.0.1:<port>/ 로 연다.
"""
# (from __future__ import annotations 제거 — FastAPI 가 함수 내부 import 한 Request 타입을 문자열로 받으면 쿼리 파라미터로 오인)
import json
import os
import secrets
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

APP_NAME = "ABC Tool"
FROZEN = getattr(sys, "frozen", False)
BASE_DIR = Path(sys.executable).parent if FROZEN else Path(__file__).resolve().parent.parent   # exe 옆 / 저장소 루트
RES_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))                                              # 번들 리소스(frontend_out, backend)
DATA_DIR = Path(os.getenv("APPDATA") or Path.home()) / "ABCTool"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = BASE_DIR / "config.json"

DEFAULT_CONFIG = {
    "port": 8765,
    "site_password": "abc",                # 화면 비밀번호(게이트). 비우면 게이트 없음
    "admin_password": "0108",              # URL 추가/삭제
    "database_url": "",                    # 비우면 PC 파일(sqlite). 공용 DB 쓰려면 postgres URL
    "gemini_api_key": "",                  # Apple Stalker AI 요약(없으면 요약 생략)
    "serpapi_key": "",                     # honeyComb Google Shopping 수집(SerpApi) — 없으면 목업만
    "email": {"enabled": False, "auto_send_after_run": False, "smtp_server": "smtp.naver.com", "smtp_port": 587,
              "sender": "", "password": "", "recipients": ""},
    "schedule": {"mode": "manual", "weekday": 0, "hour": 9, "minute": 0, "run_apple_stalker": True, "run_qubi": True,
                 "qubi_payload": {"product": "M3", "page_types": ["PDP", "Compare"], "mode": "all"},
                 "static_daily": True, "static_hour": 8,    # 공통페이지 QA — 매일 08:00 (mode 가 auto 일 때)
                 "run_honeycomb": False, "honeycomb_detail": False},  # honeyComb(SerpApi 호출 발생) 은 기본 수동 — 켜면 주간 실행에 포함
    "open_browser": True,
    "ca_bundle_path": "",                   # (선택) 회사 루트 인증서 .pem 경로 — truststore 로 안 풀릴 때
    "ssl_verify": True,                     # 최후 수단: false 면 인증서 검증 끔(사내 테스트용)
}


# [2026-09-11] 팀 공통 설정 임베드 — exe 안에 desktop/config.default.json 이 들어가 있으면(빌드 시 GitHub Secrets 로 채움)
# 누구 PC 에서 켜도 비밀번호·API 키·자동 실행 설정이 같다. 이메일(email)은 각자 PC 의 config.json 에서만 정한다.
SHARED_KEYS = ("site_password", "admin_password", "gemini_api_key", "serpapi_key", "schedule", "database_url", "port", "ca_bundle_path", "ssl_verify")


def _bundled_default() -> dict:
    for cand in (RES_DIR / "desktop" / "config.default.json", BASE_DIR / "desktop" / "config.default.json", BASE_DIR / "config.default.json"):
        if cand.exists():
            try:
                return json.loads(cand.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}


def _deep_merge(base: dict, over: dict) -> dict:
    out = json.loads(json.dumps(base))
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        elif v not in (None, ""):
            out[k] = v
    return out


def load_config() -> dict:
    bundled = _bundled_default()
    shared = {k: v for k, v in bundled.items() if k in SHARED_KEYS}
    if not CONFIG_PATH.exists():
        # 첫 실행: 임베드된 공통값으로 config.json 생성(이메일은 비움)
        CONFIG_PATH.write_text(json.dumps(_deep_merge(DEFAULT_CONFIG, shared), ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        local = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        local = {}
    # 우선순위: 기본값 < 임베드 공통값 < 이 PC 의 config.json (사람이 화면에서 바꾼 값이 최우선)
    return _deep_merge(_deep_merge(DEFAULT_CONFIG, shared), local)


def save_config(cfg: dict):
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def apply_env(cfg: dict):
    os.environ.setdefault("SITE_PASSWORD", cfg.get("site_password") or "")
    os.environ["ADMIN_PASSWORD"] = cfg.get("admin_password") or "0108"
    os.environ["DATABASE_URL"] = cfg.get("database_url") or f"sqlite:///{(DATA_DIR / 'abc_tool.db').as_posix()}"
    if cfg.get("gemini_api_key"):
        os.environ["GEMINI_API_KEY"] = cfg["gemini_api_key"]
    if cfg.get("serpapi_key"):
        os.environ["SERPAPI_KEY"] = cfg["serpapi_key"]
    elif "SERPAPI_KEY" in os.environ and not cfg.get("serpapi_key"):
        os.environ.pop("SERPAPI_KEY", None)
    os.environ.setdefault("HC_RUNS_DIR", str(DATA_DIR / "hc_runs"))
    em = cfg.get("email") or {}
    os.environ["EMAIL_REPORT_ENABLED"] = "true" if em.get("enabled") else "false"
    for k, v in (("SMTP_SERVER", em.get("smtp_server")), ("SMTP_PORT", str(em.get("smtp_port") or "")),
                 ("SENDER_EMAIL", em.get("sender")), ("SENDER_PASSWORD", em.get("password")), ("RECIPIENT_EMAIL", em.get("recipients"))):
        if v:
            os.environ[k] = str(v)
    os.environ.setdefault("CRON_TOKEN", secrets.token_hex(8))
    # 렌더 기본 OFF(큐비 v5 결정) — exe 에는 chromium 을 넣지 않는다
    os.environ.setdefault("USE_PLAYWRIGHT", "false"); os.environ.setdefault("JS_RESCUE", "false"); os.environ.setdefault("QB_SPEC_API", "true")
    os.environ.setdefault("KEEP_SNAPSHOTS", "10")
    os.environ.setdefault("QB_STATIC_DIR", str(DATA_DIR / "static_runs"))  # 공통페이지 QA 결과(매일) 저장


def apply_os_trust():
    """[2026-09-11] 사내망 SSL — 프록시가 https 를 회사 인증서로 재봉인하면 파이썬 기본 인증서 목록(certifi)만으로는
    CERTIFICATE_VERIFY_FAILED 가 난다. truststore 로 Windows/macOS 인증서 저장소를 쓰게 하면 크롬이 믿는 인증서를 그대로 믿는다.
    config.json 에 ca_bundle_path(회사 CA .pem) 가 있으면 그것도 함께 지정. 최후 수단 ssl_verify=false (경고 로그)."""
    cfg = load_config()
    try:
        import truststore
        truststore.inject_into_ssl()
        print("[launcher] SSL: OS 인증서 저장소 사용(truststore)")
    except Exception as e:
        print(f"[launcher] truststore 사용 불가({e}) — certifi 기본 목록으로 진행")
    ca = cfg.get("ca_bundle_path")
    if ca and Path(ca).exists():
        os.environ["SSL_CERT_FILE"] = ca; os.environ["REQUESTS_CA_BUNDLE"] = ca
        print(f"[launcher] SSL: CA bundle {ca}")
    if str(cfg.get("ssl_verify", True)).lower() in ("false", "0"):
        import ssl
        ssl._create_default_https_context = ssl._create_unverified_context  # noqa
        os.environ["QB_SSL_VERIFY"] = "false"
        print("[launcher] ⚠ SSL 검증 끔(ssl_verify=false) — 사내 테스트용, 가능하면 truststore/CA bundle 을 쓰세요")


def apply_windows_proxy():
    """사내망: Windows 인터넷 옵션의 프록시를 읽어 httpx/urllib 이 쓰는 환경변수로 넣는다(이미 있으면 유지)."""
    if os.name != "nt" or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY"):
        return
    try:
        import winreg  # type: ignore
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        enabled, _ = winreg.QueryValueEx(k, "ProxyEnable")
        if enabled:
            server, _ = winreg.QueryValueEx(k, "ProxyServer")
            server = str(server)
            if "=" in server:  # "http=host:port;https=host:port"
                parts = dict(p.split("=", 1) for p in server.split(";") if "=" in p)
                server = parts.get("https") or parts.get("http") or server
            proxy = server if server.startswith("http") else f"http://{server}"
            os.environ["HTTP_PROXY"] = os.environ["HTTPS_PROXY"] = proxy
            try:
                bypass, _ = winreg.QueryValueEx(k, "ProxyOverride")
                os.environ["NO_PROXY"] = str(bypass).replace(";", ",") + ",127.0.0.1,localhost"
            except Exception:
                os.environ["NO_PROXY"] = "127.0.0.1,localhost"
            print(f"[launcher] system proxy → {proxy}")
    except Exception as e:
        print(f"[launcher] proxy read skip: {e}")


def build_app(cfg: dict):
    sys.path.insert(0, str(RES_DIR / "backend"))
    sys.path.insert(0, str(RES_DIR / "backend" / "dotcom_qa"))
    os.chdir(RES_DIR / "backend")  # 상대경로(./local.db 등) 기준
    from fastapi import Request, Form
    from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse, FileResponse
    from fastapi.staticfiles import StaticFiles
    from starlette.middleware.base import BaseHTTPMiddleware
    import main as backend_main  # backend/main.py
    app = backend_main.app
    front = next((d for d in (RES_DIR / "frontend_out", BASE_DIR / "desktop" / "frontend_out") if d.exists()), RES_DIR / "frontend_out")
    site_password = cfg.get("site_password") or ""

    # ── 비밀번호 게이트(Next middleware + /api/gate-auth 대체) ──
    @app.post("/api/gate-auth")
    async def gate_auth(password: str = Form(""), next: str = Form("/")):
        if site_password and password != site_password:
            return RedirectResponse(f"/gate/?next={next}&error=1", status_code=303)
        resp = RedirectResponse(next if next.startswith("/") else "/", status_code=303)
        resp.set_cookie("as_auth", "1", max_age=600, httponly=True, samesite="lax", path="/")
        return resp

    class Gate(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            p = request.url.path
            authed = (not site_password) or request.cookies.get("as_auth") == "1"
            if p in ("/", "") and front.exists() and authed:
                return FileResponse(str(front / "index.html"))  # 백엔드의 안내용 "/" 대신 프론트 화면
            if p.startswith(("/api", "/_next", "/gate", "/desktop")) or "." in p.rsplit("/", 1)[-1] or authed:
                return await call_next(request)
            return RedirectResponse(f"/gate/?next={p}", status_code=302)
    app.add_middleware(Gate)

    # ── 설정 API + 설정 페이지(스케줄/메일 자동·수동) ──
    @app.get("/api/settings")
    def get_settings():
        c = load_config(); c = json.loads(json.dumps(c)); c["email"]["password"] = "***" if c["email"].get("password") else ""
        c["serpapi_key"] = ("***" + c["serpapi_key"][-4:]) if c.get("serpapi_key") else ""
        return {"config": c, "config_path": str(CONFIG_PATH), "data_dir": str(DATA_DIR), "database": os.environ.get("DATABASE_URL", "").split("@")[-1]}

    @app.post("/api/settings")
    async def set_settings(request: Request):
        body = await request.json(); c = load_config()
        for k in ("schedule", "email"):
            if isinstance(body.get(k), dict):
                if k == "email" and body[k].get("password") == "***":
                    body[k]["password"] = c["email"].get("password", "")
                c[k].update(body[k])
        for k in ("site_password", "admin_password", "gemini_api_key", "serpapi_key", "database_url", "open_browser", "port"):
            if k in body and not (k == "serpapi_key" and str(body[k]).startswith("***")):
                c[k] = body[k]
        save_config(c); apply_env(c)
        return {"ok": True, "note": "포트·DB 변경은 재시작 후 적용"}

    @app.get("/desktop/settings", response_class=HTMLResponse)
    def settings_page():
        return (RES_DIR / "desktop" / "settings.html").read_text(encoding="utf-8") if (RES_DIR / "desktop" / "settings.html").exists() \
            else (BASE_DIR / "desktop" / "settings.html").read_text(encoding="utf-8")

    @app.post("/api/settings/run-now")
    async def run_now():
        threading.Thread(target=lambda: scheduled_job(load_config(), manual=True), daemon=True).start()
        return {"ok": True}

    # ── 정적 프론트(Next export) — API 가 아닌 경로는 index.html 폴백 ──
    if front.exists():
        app.mount("/_next", StaticFiles(directory=str(front / "_next")), name="next")

        @app.get("/{path:path}")
        async def spa(path: str):
            cand = front / path
            if path and cand.is_file():
                return FileResponse(str(cand))
            if (cand / "index.html").is_file():
                return FileResponse(str(cand / "index.html"))
            return FileResponse(str(front / "index.html"))
    return app


def scheduled_job(cfg: dict, manual: bool = False):
    """주간 실행: Apple Stalker 전체 크롤 → (옵션) 메일, 큐비 기본 검수."""
    import httpx
    port = cfg.get("port", 8765); base = f"http://127.0.0.1:{port}"
    sch = cfg.get("schedule") or {}; em = cfg.get("email") or {}
    print(f"[scheduler] job start ({'manual' if manual else 'auto'}) {datetime.now():%Y-%m-%d %H:%M}")
    with httpx.Client(timeout=3600, trust_env=False) as c:
        if sch.get("run_apple_stalker", True):
            try:
                r = c.get(f"{base}/api/cron/tick", params={"token": os.environ.get("CRON_TOKEN", "")})
                print("[scheduler] apple stalker:", r.status_code)
            except Exception as e:
                print("[scheduler] apple stalker fail:", e)
        if sch.get("run_qubi", True):
            try:
                r = c.post(f"{base}/api/qb/run", json=sch.get("qubi_payload") or {"product": "M3", "page_types": ["PDP", "Compare"], "mode": "all"})
                print("[scheduler] qubi:", r.status_code, r.text[:120])
            except Exception as e:
                print("[scheduler] qubi fail:", e)
        if sch.get("run_honeycomb"):
            try:
                r = c.post(f"{base}/api/hc/run", json={"detail": bool(sch.get("honeycomb_detail", False))})
                print("[scheduler] honeycomb:", r.status_code, r.text[:120])
            except Exception as e:
                print("[scheduler] honeycomb fail:", e)
        # 메일: cron_tick 이 EMAIL_REPORT_ENABLED 에 따라 발송 — auto_send_after_run 이 꺼져 있으면 건너뛰도록 env 조정
    print("[scheduler] job done")


def static_job(cfg: dict):
    import httpx
    try:
        with httpx.Client(timeout=60, trust_env=False) as c:
            r = c.post(f"http://127.0.0.1:{cfg.get('port', 8765)}/api/qb/static/run", json={})
            print("[scheduler] 공통페이지 QA:", r.status_code, r.text[:80])
    except Exception as e:
        print("[scheduler] static qa fail:", e)


def scheduler_loop():
    last_key = None; last_static = None
    while True:
        try:
            cfg = load_config(); sch = cfg.get("schedule") or {}
            em = cfg.get("email") or {}
            os.environ["EMAIL_REPORT_ENABLED"] = "true" if (em.get("enabled") and em.get("auto_send_after_run")) else "false"
            now = datetime.now()
            key = f"{now:%Y-%m-%d}"
            if sch.get("mode") == "auto" and now.weekday() == int(sch.get("weekday", 0)) and now.hour == int(sch.get("hour", 9)) \
               and now.minute >= int(sch.get("minute", 0)) and last_key != key:
                last_key = key
                scheduled_job(cfg)
            # 공통페이지 QA — 매일(auto 모드일 때)
            if sch.get("mode") == "auto" and sch.get("static_daily", True) and now.hour == int(sch.get("static_hour", 8)) and last_static != key:
                last_static = key
                static_job(cfg)
        except Exception as e:
            print("[scheduler] loop error:", e)
        time.sleep(60)


def main():
    cfg = load_config()
    apply_env(cfg); apply_windows_proxy(); apply_os_trust()
    app = build_app(cfg)
    port = int(cfg.get("port", 8765))
    threading.Thread(target=scheduler_loop, daemon=True).start()
    if cfg.get("open_browser", True):
        threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{port}/")).start()
    import uvicorn
    print(f"[launcher] {APP_NAME} → http://127.0.0.1:{port}/   (설정: http://127.0.0.1:{port}/desktop/settings)  config: {CONFIG_PATH}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
