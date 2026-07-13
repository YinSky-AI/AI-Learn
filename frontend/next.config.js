/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    domains: ["localhost"],
    remotePatterns: [
      {
        protocol: "https",
        hostname: "**",
      },
    ],
  },
  async rewrites() {
    // 运行时读取后端地址（Docker 中为 http://backend:8000，本地开发为 http://localhost:8000）
    const apiBase = process.env.API_PROXY_TARGET || "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${apiBase}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
