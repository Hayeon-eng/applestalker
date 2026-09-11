# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — ABC Tool (FastAPI 백엔드 + 정적 프론트 + 데이터 파일) 을 한 폴더(onedir)로.
# onefile 대신 onedir 를 쓰는 이유: 실행 속도(매번 압축 해제 없음)와 sqlite/json 데이터 파일 경로 안정성.
import os, glob
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

here = os.path.abspath(os.path.dirname(SPEC)) if 'SPEC' in globals() else os.getcwd()
root = os.path.abspath(os.path.join(here, '..'))

datas = []
# 프론트 정적 파일
datas.append((os.path.join(here, 'frontend_out'), 'frontend_out'))
datas.append((os.path.join(here, 'settings.html'), 'desktop'))
if os.path.exists(os.path.join(here, 'config.default.json')):
    datas.append((os.path.join(here, 'config.default.json'), 'desktop'))  # 팀 공통 설정(빌드 시 Secrets 로 채움)
# 백엔드 데이터(JSON 룰·레지스트리·시드) — 코드 옆 상대경로로 읽으므로 같은 구조로 복사
for pattern in ('backend/dotcom_qa/*.json', 'backend/honeycomb/*.json', 'backend/honeycomb/*.json.gz', 'backend/*.json'):  # .gz 도 포함(honeyComb 목업)
    for f in glob.glob(os.path.join(root, pattern)):
        datas.append((f, os.path.dirname(os.path.relpath(f, root))))
# 백엔드 파이썬 소스 자체도 리소스로 (런처가 sys.path 에 RES_DIR/backend 를 추가해 import)
for f in glob.glob(os.path.join(root, 'backend', '**', '*.py'), recursive=True):
    if '__pycache__' in f: continue
    datas.append((f, os.path.dirname(os.path.relpath(f, root))))

hidden = (collect_submodules('uvicorn') + collect_submodules('sqlalchemy') + collect_submodules('openpyxl')
          + collect_submodules('pptx') + collect_submodules('httpx') + collect_submodules('bs4') + collect_submodules('lxml')
          + ['multipart', 'anyio', 'sniffio', 'h11', 'psycopg2', 'loguru', 'dotenv', 'PIL'])
datas += collect_data_files('pptx') + collect_data_files('certifi')

a = Analysis([os.path.join(here, 'launcher.py')], pathex=[root, os.path.join(root, 'backend'), os.path.join(root, 'backend', 'dotcom_qa')],
             binaries=[], datas=datas, hiddenimports=hidden, hookspath=[], runtime_hooks=[],
             excludes=['playwright', 'tkinter', 'matplotlib', 'tensorflow', 'torch'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='ABC_Tool', console=True,  # console=True: 로그 창(문제 진단용). 안정화 후 False 가능
          icon=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='ABC_Tool')
