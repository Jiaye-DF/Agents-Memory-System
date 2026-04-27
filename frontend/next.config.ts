import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Coolify Docker 部署用：產出 .next/standalone（含 server.js + 最小 deps）
  output: "standalone",
  // build 階段不跑 TS check，避免在資源吃緊的 Coolify host OOM。
  // TS error 改由 dev (`next dev`) 與 CI 抓，部署 pipeline 不二次驗證
  typescript: {
    ignoreBuildErrors: true,
  },
};

export default nextConfig;
