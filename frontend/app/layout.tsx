import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Live Event Analytics",
  description: "SQL-driven event analytics dashboard for the assignment pipeline.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
