import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ??
      'https://matchbridge-creator-selection-agent.maple-owlet-9574.chatgpt.site',
  ),
  title: 'MatchBridge 智选 · Campaign选号工作台',
  description:
    '面向品牌业务团队的可解释达人匹配、风险审核、预算组合优化与人工确认工作台。',
  openGraph: {
    title: 'MatchBridge 智选',
    description: 'Campaign 选号与人工确认工作台',
    images: [{ url: '/og.png', width: 1731, height: 909 }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'MatchBridge 智选',
    description: 'Campaign 选号与人工确认工作台',
    images: ['/og.png'],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
