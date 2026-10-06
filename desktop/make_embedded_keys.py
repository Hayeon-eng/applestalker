"""
make_embedded_keys.py — [2026-10] 팀 공용 API 키를 "코드 안에만" 넣기 위한 생성기 (관리자 PC 에서만 실행)

  python desktop/make_embedded_keys.py
    → Gemini / SerpApi 키를 물어본 뒤 desktop/embedded_keys.py 를 만든다.
    → 이 파일은 .gitignore 에 올라가 있어 저장소(GitHub)에는 절대 들어가지 않고, 로컬 build.ps1 로 만든 exe 에만 포함된다.
    → 런처는 config.json 의 키가 비어 있을 때만 이 파일의 키를 쓴다. 첫 실행에 만들어지는 config.json 에는 키가 비어 있다.

  ⚠ 이것은 "보안"이 아니라 "실수로 노출되는 것을 막는" 수준입니다.
    base64+XOR 로 감쌌지만 exe 를 받은 사람이 마음먹으면 1분 안에 꺼낼 수 있습니다(pyinstxtractor 등).
    키를 진짜로 숨기려면 키를 서버(릴레이)에 두고 PC 에서는 토큰만 보내는 구조여야 합니다. 팀 내부 배포 전제에서만 쓰세요.
"""
import base64
import getpass
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "embedded_keys.py")
# 난독화용 고정 키 — 비밀이 아니다(코드에 그대로 있음). 눈으로 봐서 키처럼 안 보이게 하는 용도.
_X = b"ABCTool-embedded-keys-2026"


def wrap(s: str) -> str:
    b = s.encode("utf-8")
    x = bytes(c ^ _X[i % len(_X)] for i, c in enumerate(b))
    return base64.b85encode(x).decode("ascii")


def main():
    print("ABC Tool — 임베드 키 생성 (빈칸 Enter = 넣지 않음)")
    gemini = getpass.getpass("Gemini API 키: ").strip()
    serp = getpass.getpass("SerpApi 키   : ").strip()
    if not gemini and not serp:
        print("입력된 키가 없어 만들지 않았습니다."); return 1
    body = f'''# embedded_keys.py — 자동 생성(desktop/make_embedded_keys.py). 저장소에 커밋 금지(.gitignore).
# 값은 base64(b85)+XOR 로 감싼 것일 뿐 암호화가 아닙니다. 런처(launcher.py)의 _embedded_keys() 가 풉니다.
_K = {{
    "gemini_api_key": {wrap(gemini)!r},
    "serpapi_key": {wrap(serp)!r},
}}
'''
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(body)
    print(f"→ {OUT} 생성 (gemini={'O' if gemini else '-'}, serpapi={'O' if serp else '-'})")
    print("   이제 desktop\\build.ps1 로 빌드하면 exe 에 포함됩니다. GitHub Actions 빌드에는 포함되지 않습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
