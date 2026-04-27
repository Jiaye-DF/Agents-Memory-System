import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Coolify Docker 部署用：產出 .next/standalone（含 server.js + 最小 deps）
  output: "standalone",
};

export default nextConfig;
