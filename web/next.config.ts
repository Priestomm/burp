import type { NextConfig } from "next";

const API = process.env.BURP_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  // Dish photos are files of the Python API; the browser only ever talks to Next.
  rewrites() {
    return [{ source: "/api/media/:path*", destination: `${API}/api/media/:path*` }];
  },
};

export default nextConfig;
