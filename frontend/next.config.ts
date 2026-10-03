import type { NextConfig } from "next";

const backendUrl = (process.env.FINLENS_API_BASE_URL || "http://127.0.0.1:8000")
  .replace(/\/$/, "");

const nextConfig: NextConfig = {
  async rewrites() {
    return [{
      source: "/api/finlens/:path*",
      destination: `${backendUrl}/:path*`,
    }];
  },
};

export default nextConfig;
