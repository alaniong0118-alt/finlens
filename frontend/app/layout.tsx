import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FinLens | SEC Filing Research",
  description: "Ask financial questions and inspect the SEC filing evidence behind each answer.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
