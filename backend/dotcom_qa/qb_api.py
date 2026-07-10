"""
qb_api.py — 큐비 — Dotcom QA 체커 [분할 후 집결자]

큐비 🐝 — 풀네임 QA Bee. 990줄 단일 파일이 커져 도메인별 모듈로 분할했다.
이 파일은 하위호환 유지를 위한 얇은 집결자 — main.py는 그대로:
    from dotcom_qa.qb_api import qb_router, set_fetcher  (또는 enable_default_crawler)

구성:
  qb_core.py             공유 인프라(라우터·registry·fetcher·LAST_RESULTS·헬퍼)
  qb_routes_check.py     /rules, /check, /check-url, /check-html-qa
  qb_routes_run.py       /run, /run-status, /run-progress (백그라운드 대량 검수)
  qb_routes_history.py   /history*, /overview, /report.xlsx, /email-draft
  qb_routes_manage.py    /sites*, /products*, /specs*, /rules/*/add (V2 편집 차단 포함)
  qb_routes_specrules.py /spec-rules*, /spec-check (Rule DB V2)
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))  # 패키지/스크립트 양쪽에서 flat import 허용

from qb_core import qb_router, set_fetcher, enable_default_crawler  # noqa: F401  (재수출)

# 라우트 등록(임포트 부수효과로 qb_router에 엔드포인트가 붙는다)
import qb_routes_check    # noqa: F401,E402
import qb_routes_run      # noqa: F401,E402
import qb_routes_history  # noqa: F401,E402
import qb_routes_manage   # noqa: F401,E402
import qb_routes_specrules  # noqa: F401,E402
