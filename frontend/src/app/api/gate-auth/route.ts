import { NextRequest, NextResponse } from 'next/server';

// 비번은 환경변수 SITE_PASSWORD로 덮어쓸 수 있음(권장). 없으면 기본값 사용.
const SITE_PASSWORD = process.env.SITE_PASSWORD || 'ocg2022!';

// Render 등 리버스 프록시 뒤에서는 req.url이 내부 호스트(localhost:포트)로 잡히는 경우가 있어
// x-forwarded-host / x-forwarded-proto를 우선으로 실제 공개 도메인을 재구성한다.
function publicOrigin(req: NextRequest): string {
  const proto = req.headers.get('x-forwarded-proto') || req.nextUrl.protocol.replace(':', '');
  const host = req.headers.get('x-forwarded-host') || req.headers.get('host') || req.nextUrl.host;
  return `${proto}://${host}`;
}

export async function POST(req: NextRequest) {
  const form = await req.formData();
  const password = String(form.get('password') || '');
  const next = String(form.get('next') || '/');
  const origin = publicOrigin(req);

  if (password !== SITE_PASSWORD) {
    const url = new URL('/gate', origin);
    url.searchParams.set('next', next);
    url.searchParams.set('error', '1');
    return NextResponse.redirect(url, 303);
  }

  const url = new URL(next.startsWith('/') ? next : '/', origin);
  const res = NextResponse.redirect(url, 303);
  res.cookies.set('as_auth', '1', {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production', // 로컬(http)에서도 쿠키가 저장되도록
    sameSite: 'lax',
    path: '/',
    // maxAge를 주지 않으면 세션 쿠키가 되어 브라우저를 완전히 닫으면 사라짐
    // → 다음에 다시 열 때는 비밀번호를 또 입력해야 함
  });
  return res;
}
