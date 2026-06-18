import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Apple Tracker - Competitive Intelligence Dashboard',
  description: 'Monitor Apple.com and Samsung.com changes with automated competitive intelligence',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="bg-gray-50">{children}</body>
    </html>
  )
}
