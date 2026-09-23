import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LyNote",
  description: "个人外脑知识平台：筛资料、建图谱、带着证据学习与判断",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,500;8..60,600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen bg-ink text-paper antialiased">{children}</body>
    </html>
  );
}
