import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "OdailySeer - Polymarket 概率异动监控",
  description: "Polymarket 概率异动、上新、尾盘发现与大额数据追踪",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen antialiased">
        <nav className="border-b border-[#21262d] bg-[#161b22]">
          <div className="mx-auto flex max-w-[1120px] items-center gap-6 overflow-x-auto px-4 py-3">
            <Link href="/" className="text-sm font-bold text-[#e1e4e8]">
              OdailySeer
            </Link>
            <Link
              href="/"
              className="text-sm text-[#8b949e] transition-colors hover:text-[#e1e4e8]"
            >
              异动监控
            </Link>
            <Link
              href="/analyze"
              className="text-sm text-[#8b949e] transition-colors hover:text-[#e1e4e8]"
            >
              市场分析
            </Link>
            <Link
              href="/new-markets"
              className="text-sm text-[#8b949e] transition-colors hover:text-[#e1e4e8]"
            >
              Polymarket上新
            </Link>
            <Link
              href="/late-markets"
              className="text-sm text-[#8b949e] transition-colors hover:text-[#e1e4e8]"
            >
              尾盘发现
            </Link>
            <Link
              href="/whale-alerts"
              className="text-sm text-[#8b949e] transition-colors hover:text-[#e1e4e8]"
            >
              大额监控
            </Link>
            <Link
              href="/whale-trades"
              className="text-sm text-[#8b949e] transition-colors hover:text-[#e1e4e8]"
            >
              大额活动
            </Link>
            <Link
              href="/world-cup"
              className="text-sm text-[#8b949e] transition-colors hover:text-[#e1e4e8]"
            >
              世界杯
            </Link>
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
