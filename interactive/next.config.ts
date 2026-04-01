import type { NextConfig } from "next";

const isProd = process.env.NODE_ENV === "production";

const nextConfig: NextConfig = {
  output: "export",
  basePath: isProd ? "/emotion-engine/interactive" : "",
  assetPrefix: isProd ? "/emotion-engine/interactive/" : "",
  images: { unoptimized: true },
};

export default nextConfig;
