import { NextRequest, NextResponse } from 'next/server';

// 비번은 환경변수 SITE_PASSWORD로 덮어쓸 수 있음(권장). 없으면 기본값 사용.
const SITE_PASSWORD = process.env.SITE_PASSWORD || 'ocg2022!';

export async function POST(req: NextRequest) {
  let password = '';
  try {
    const body = await req.json();
    password = body?.password || '';
  } catch {
    // ignore
  }

  if (password !== SITE_PASSWORD) {
    return NextResponse.json({ ok: false, error: '비밀번호가 틀렸습니다.' }, { status: 401 });
  }

  const res = NextResponse.json({ ok: true });
  res.cookies.set('as_auth', '1', {
    httpOnly: true,
    secure: true,
    sameSite: 'lax',
    path: '/',
    // maxAge를 주지 않으면 세션 쿠키가 되어 브라우저를 완전히 닫으면 사라짐
    // → 다음에 다시 열 때는 비밀번호를 또 입력해야 함
  });
  return res;
}
