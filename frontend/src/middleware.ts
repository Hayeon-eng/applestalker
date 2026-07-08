import { NextRequest, NextResponse } from 'next/server';

// 사이트 전체 비밀번호 게이트.
// AS_AUTH 쿠키가 없으면 /gate(비번 입력 화면)로 보냄.
// /gate 자체, 비번 확인 API, Next.js 정적 리소스는 통과시켜야 무한 리다이렉트가 안 남.
const PUBLIC_PATHS = ['/gate', '/api/gate-auth'];

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  const isPublic =
    PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + '/')) ||
    pathname.startsWith('/_next') ||
    pathname.startsWith('/favicon') ||
    /\.(png|jpg|jpeg|svg|webp|ico|css|js|map)$/.test(pathname);

  if (isPublic) return NextResponse.next();

  const authed = req.cookies.get('as_auth')?.value === '1';
  if (authed) return NextResponse.next();

  // Render 등 프록시 뒤에서 req.url이 내부 호스트로 잡히는 경우가 있어 forwarded 헤더 우선 사용
  const proto = req.headers.get('x-forwarded-proto') || req.nextUrl.protocol.replace(':', '');
  const host = req.headers.get('x-forwarded-host') || req.headers.get('host') || req.nextUrl.host;
  const gateUrl = new URL('/gate', `${proto}://${host}`);
  gateUrl.searchParams.set('next', pathname);
  return NextResponse.redirect(gateUrl);
}

export const config = {
  // API 라우트는 각자 필요하면 자체 인증을 두므로 미들웨어에서는 페이지만 막음
  matcher: ['/((?!api).*)'],
};
