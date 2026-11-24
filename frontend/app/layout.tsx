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
      <body><aside role="note" data-testid="finlens-synthetic-trial-banner" style={{position:"sticky",top:0,zIndex:1000,padding:"12px 16px",background:"#fff3cd",color:"#402b00",fontWeight:700}}>SYNTHETIC DEMO ONLY. Not real SEC financial results. Placeholder references are not live evidence.</aside>{children}</body>
    </html>
  );
}
