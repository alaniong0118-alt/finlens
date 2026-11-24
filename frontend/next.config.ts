import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

const config = (phase: string): NextConfig => ({
  distDir: phase === PHASE_DEVELOPMENT_SERVER ? ".next" : ".next-prod",
  async headers() {
    return [{ source: "/:path*", headers: [
      { key: "Content-Security-Policy", value: "connect-src 'self'; form-action 'self'; object-src 'none'; base-uri 'self'" },
      { key: "Referrer-Policy", value: "no-referrer" },
    ] }];
  },
});

export default config;
