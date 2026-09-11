/** @type {import('next').NextConfig} */
// [2026-09] NEXT_EXPORT=1 이면 데스크톱(exe)용 정적 내보내기 — FastAPI 가 out/ 을 그대로 서빙한다.
//  · 정적 내보내기에서는 src/middleware.ts 와 src/app/api/* (Next 서버 기능)를 쓸 수 없어 desktop/build.ps1 이
//    빌드 중 잠시 옆으로 치워두고, 같은 기능(비밀번호 게이트)은 desktop/launcher.py 의 FastAPI 미들웨어가 담당한다.
const isExport = !!process.env.NEXT_EXPORT;
module.exports = {
  reactStrictMode: true,
  ...(isExport ? { output: "export", trailingSlash: true, images: { unoptimized: true } } : {}),
};
