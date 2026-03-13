import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OdailySeer - Polymarket 概率异动监控",
  description: "Polymarket 概率异动监控与 AI 原因分析",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
