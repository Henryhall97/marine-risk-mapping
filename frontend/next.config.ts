import type { NextConfig } from "next";

// Large/copyrighted static assets (whale GLBs, species reference photos, ID
// wizard images) live under frontend/public/{models,species,wizard} but are
// gitignored — they are served from the API host's Caddy at /static/*.
//
// In production we rewrite the well-known paths to that origin so existing
// component code (e.g. <img src="/species/foo.jpg">) keeps working.  Locally
// (next dev) the rewrites are skipped and Next serves the files directly
// from frontend/public, so editing assets gives instant feedback.
const STATIC_ORIGIN =
  process.env.NEXT_PUBLIC_STATIC_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "";

const STATIC_PREFIXES = ["models", "species", "wizard"] as const;

const nextConfig: NextConfig = {
  reactStrictMode: false,
  images: {
    remotePatterns: [
      { protocol: "http", hostname: "localhost", port: "8000" },
      { protocol: "https", hostname: "api.whalewatch.uk" },
    ],
  },
  transpilePackages: [
    "@deck.gl/core",
    "@deck.gl/react",
    "@deck.gl/layers",
    "@deck.gl/geo-layers",
  ],
  async rewrites() {
    if (!STATIC_ORIGIN) return [];
    const origin = STATIC_ORIGIN.replace(/\/$/, "");
    return STATIC_PREFIXES.map((p) => ({
      source: `/${p}/:path*`,
      destination: `${origin}/static/${p}/:path*`,
    }));
  },
  webpack: (config) => {
    // h3-js v4 uses WebAssembly
    config.experiments = {
      ...config.experiments,
      asyncWebAssembly: true,
    };
    return config;
  },
};

export default nextConfig;
