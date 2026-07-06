import './globals.css';
import './globals-components.css';
import type { Metadata } from 'next';
export const metadata: Metadata = {
  title: 'Apple Stalker',
  description: '경쟁사 웹 변화 감지 · AEO 인텔리전스',
};
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (<html lang="ko"><body>{children}</body></html>);
}
