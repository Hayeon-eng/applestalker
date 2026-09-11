# desktop/build.ps1 — Windows 에서 ABC_Tool.exe 빌드 (GitHub Actions windows-latest 또는 로컬 PC)
#   전제: Node 20+, Python 3.11+, 인터넷(npm/pip). 결과: desktop/dist/ABC_Tool/ABC_Tool.exe (+ config.example.json, README_실행.txt)
$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\.."
Set-Location $root

Write-Host "== 1) 프론트 정적 빌드 (Next export)"
Set-Location "$root\frontend"
# 정적 내보내기에서 쓸 수 없는 Next 서버 기능(비밀번호 게이트 API·미들웨어)을 잠시 치운다 — 같은 기능은 launcher.py 가 담당
if (Test-Path "src\app\api") { Rename-Item "src\app\api" "_api_disabled" }
if (Test-Path "src\middleware.ts") { Rename-Item "src\middleware.ts" "_middleware.ts.disabled" }
try {
  $env:NEXT_EXPORT = "1"; $env:NEXT_PUBLIC_API_URL = "/"
  npm ci
  npm run build
} finally {
  if (Test-Path "src\_api_disabled") { Rename-Item "src\_api_disabled" "api" }
  if (Test-Path "src\_middleware.ts.disabled") { Rename-Item "src\_middleware.ts.disabled" "middleware.ts" }
}
if (Test-Path "$root\desktop\frontend_out") { Remove-Item -Recurse -Force "$root\desktop\frontend_out" }
Copy-Item -Recurse "out" "$root\desktop\frontend_out"

Write-Host "== 2) 파이썬 의존성 + PyInstaller"
Set-Location $root
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
# playwright 는 requirements 에 있지만 chromium 은 설치하지 않는다(렌더 기본 OFF)

Write-Host "== 3) exe 빌드"
Set-Location "$root\desktop"
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
pyinstaller --noconfirm abc_tool.spec

Copy-Item "config.example.json" "dist\ABC_Tool\config.example.json"
Copy-Item "README_실행.txt" "dist\ABC_Tool\README_실행.txt"
Write-Host "== 완료: desktop\dist\ABC_Tool\ABC_Tool.exe"
