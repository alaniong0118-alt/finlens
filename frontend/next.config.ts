import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

const backendUrl = (process.env.FINLENS_API_BASE_URL || "http://127.0.0.1:8000")
  .replace(/\/$/, "");

const nextConfig = (phase: string): NextConfig => ({
  // Keep dev output from replacing CSS/chunks used by a running production server.
  distDir: phase === PHASE_DEVELOPMENT_SERVER ? ".next" : ".next-prod",
  async rewrites() {
    return [{
      source: "/api/finlens/:path*",
      destination: `${backendUrl}/:path*`,
    }];
  },
});

export default nextConfig;
