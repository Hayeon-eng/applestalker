ABC Tool (Apple Stalker · QA Bee · honeyComb) — PC 실행판

1. ABC_Tool.exe 를 더블클릭하면 검은 로그 창이 뜨고 잠시 후 브라우저가 http://127.0.0.1:8765/ 로 열립니다.
   (SmartScreen 경고가 나오면 "추가 정보 → 실행")
2. 처음 실행 시 exe 옆에 config.json 이 생깁니다(비밀번호·이메일·자동 실행). 화면에서 바꾸려면
   http://127.0.0.1:8765/desktop/settings
   · API 키(Gemini·SerpApi)는 관리자가 빌드한 프로그램에 내장돼 있어 config.json 에 적지 않아도 됩니다.
     (config.json 에 키를 적으면 그 값이 우선합니다. 설정 화면의 "접속·키"에서 설정 여부만 확인 가능)
3. 검수 이력은 %APPDATA%\ABCTool\ 아래에 저장됩니다(업데이트해도 유지).
   · abc_tool.db   : 큐비 검수 이력, Apple Stalker 크롤 이력
   · static_runs\  : 공통페이지 QA 결과 JSON
   · hc_runs\      : honeyComb 수집 결과 JSON
   다른 사람과 공유는 큐비 사이드바 "⬇ 이력 내보내기 / ⬆ 이력 가져오기"(JSON 파일)로 합니다.
   과거 이력을 지우려면 설정 화면(/desktop/settings) 맨 아래 "이력 초기화"를 쓰세요.
4. 자동 실행(주 1회): 설정에서 "자동" + 요일·시각을 정하면 exe 가 켜져 있는 동안 스스로 실행합니다.
   메일 자동 발송은 SMTP 정보를 넣고 "자동 발송"을 켜면 실행 후 보냅니다. 끄면 "메일 본문 복사"로 수동 발송.
5. 사내망: Windows 인터넷 옵션의 프록시를 자동으로 읽습니다. 사외(재택)에서는 그냥 직접 연결됩니다.
6. 종료: 로그 창을 닫으면 프로그램이 끝납니다.
