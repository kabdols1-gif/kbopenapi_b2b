import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OpenAPI Test",
  description: "OpenAPI 테스트 환경에서 Broker별 샘플 API를 바로 호출하고 검증할 수 있는 페이지입니다.",
  icons: {
    icon: "/openapi-favicon.svg?v=20260613",
    shortcut: "/openapi-favicon.svg?v=20260613",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body className="antialiased min-h-screen">{children}</body>
    </html>
  );
}
