import { NextRequest, NextResponse } from 'next/server';

// 비번은 환경변수 SITE_PASSWORD로 덮어쓸 수 있음(권장). 없으면 기본값 사용.
const SITE_PASSWORD = process.env.SITE_PASSWORD || 'ocg2022!';

export async function POST(req: NextRequest) {
  const form = await req.formData();
  const password = String(form.get('password') || '');
  const next = String(form.get('next') || '/');

  const url = req.nextUrl.clone();

  if (password !== SITE_PASSWORD) {
    url.pathname = '/gate';
    url.search = '';
    url.searchParams.set('next', next);
    url.searchParams.set('error', '1');
    return NextResponse.redirect(url, 303);
  }

  url.pathname = next.startsWith('/') ? next : '/';
  url.search = '';
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
