# embedded_keys.example.py — 형태 참고용. 실제 파일(embedded_keys.py)은 desktop/make_embedded_keys.py 로 만들며 커밋하지 않는다.
_K = {
    "gemini_api_key": "",   # make_embedded_keys.py 가 base64(b85)+XOR 로 감싼 문자열을 넣는다
    "serpapi_key": "",
}
