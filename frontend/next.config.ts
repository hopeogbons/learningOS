import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  output: "standalone",
  distDir: process.env.LEARNING_OS_DIST_DIR ?? ".next",
  /* config options here */
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.LEARNING_OS_BACKEND_URL ?? "http://127.0.0.1:8000"}/api/v1/:path*`,
      },
    ];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
