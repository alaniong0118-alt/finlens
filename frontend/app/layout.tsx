import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FinLens | SEC Filing Research",
  description: "Research public-company financial data, historical metrics and SEC evidence. AI analysis is optional.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: `(function(){var t='system';try{var p=localStorage.getItem('finlens-theme');if(p==='light'||p==='dark')t=p;}catch(e){}document.documentElement.dataset.theme=t==='system'?(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'):t;})();` }} /></head>
      <body>{children}</body>
    </html>
  );
}
