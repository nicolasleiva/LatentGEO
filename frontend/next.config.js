const path = require("path");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    domains: ["localhost"],
    unoptimized: true,
  },
  env: {
    NEXT_PUBLIC_API_URL:
      process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  },
  compress: true,
  poweredByHeader: false,
  generateEtags: true,
  outputFileTracingRoot: path.join(__dirname),
  // Experimental features
  experimental: {
    optimizePackageImports: ["lucide-react"],
  },
  // NOTE: 'standalone' output requires admin privileges on Windows for symlinks
  // For Docker builds, it works correctly since Docker runs as root.
  // We disable it on Windows local environment to avoid EPERM errors.
  output: process.platform === "win32" ? undefined : "standalone",
  distDir: ".next",
  // Webpack configuration for optimization
  webpack: (config, { isServer }) => {
    // Optimize bundle size
    if (!isServer) {
      config.optimization = {
        ...config.optimization,
        splitChunks: {
          chunks: "all",
          cacheGroups: {
            vendor: {
              test: /[\\/]node_modules[\\/]/,
              name: "vendors",
              chunks: "all",
            },
          },
        },
      };
    }
    return config;
  },
};

module.exports = nextConfig;
