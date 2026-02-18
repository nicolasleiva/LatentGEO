/** @type {import('next').NextConfig} */
const isProd =
  process.env.NODE_ENV === "production" ||
  process.env.ENVIRONMENT === "production";

const rawApiUrl =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  "";
const apiOrigin = (() => {
  try {
    return rawApiUrl ? new URL(rawApiUrl).origin : "";
  } catch {
    return rawApiUrl;
  }
})();

const wsOrigin = apiOrigin ? apiOrigin.replace(/^http/, "ws") : "";
const auth0Origin = process.env.AUTH0_DOMAIN
  ? `https://${process.env.AUTH0_DOMAIN}`
  : "";

if (isProd && !apiOrigin) {
  throw new Error(
    "NEXT_PUBLIC_API_URL or API_URL is required to build for production",
  );
}

const connectSrc = [
  "'self'",
  apiOrigin,
  wsOrigin,
  auth0Origin,
  "https://api.github.com",
  "https://api.hubspot.com",
  "https://integrate.api.nvidia.com",
  "https://www.googleapis.com",
].filter(Boolean);

const nextConfig = {
  // ===== DOCKER OPTIMIZATION =====
  // Standalone output for minimal production image
  output: "standalone",

  // ===== MEMORY OPTIMIZATIONS =====
  // Reduce memory usage in Docker containers
  experimental: {
    // Optimize file watching to prevent ENOMEM errors
    turbotrace: {
      logLevel: "error",
    },
  },

  // Disable type checking during build (run separately to save memory)
  typescript: {
    ignoreBuildErrors: true,
  },

  // Disable eslint during build (run separately to save memory)
  eslint: {
    ignoreDuringBuilds: true,
  },

  // Webpack memory optimization
  webpack: (config, { isServer }) => {
    // Reduce memory usage during build
    config.optimization = {
      ...config.optimization,
      minimize: true,
      removeAvailableModules: true,
      removeEmptyChunks: true,
      mergeDuplicateChunks: true,
    };

    // Limit concurrent operations
    config.infrastructureLogging = {
      level: "error",
    };

    return config;
  },

  images: {
    unoptimized: true,
  },

  // ===== PRODUCTION SECURITY HEADERS =====
  async headers() {
    return [
      {
        // Apply these headers to all routes
        source: "/:path*",
        headers: [
          // Prevent MIME type sniffing
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          // Prevent clickjacking
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          // XSS protection (legacy but still useful)
          {
            key: "X-XSS-Protection",
            value: "1; mode=block",
          },
          // HSTS - Force HTTPS (enable in production)
          {
            key: "Strict-Transport-Security",
            value: "max-age=31536000; includeSubDomains; preload",
          },
          // Referrer policy
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          // Permissions policy - disable unnecessary features
          {
            key: "Permissions-Policy",
            value: "geolocation=(), microphone=(), camera=(), payment=()",
          },
          // Content Security Policy
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://apis.google.com https://www.googletagmanager.com",
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
              "font-src 'self' https://fonts.gstatic.com data:",
              "img-src 'self' data: https: blob:",
              `connect-src ${connectSrc.join(" ")}`,
              "frame-ancestors 'none'",
              "form-action 'self'",
              "base-uri 'self'",
              "object-src 'none'",
              "upgrade-insecure-requests",
            ].join("; "),
          },
          // Prevent caching of sensitive pages
          {
            key: "Cache-Control",
            value: "no-store, max-age=0",
          },
        ],
      },
      {
        // Allow caching for static assets
        source: "/static/:path*",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=31536000, immutable",
          },
        ],
      },
      {
        // API routes - prevent caching
        source: "/api/:path*",
        headers: [
          {
            key: "Cache-Control",
            value: "no-store, no-cache, must-revalidate",
          },
        ],
      },
    ];
  },

  // ===== PRODUCTION OPTIMIZATIONS =====
  poweredByHeader: false, // Hide "X-Powered-By: Next.js"
  reactStrictMode: true,

  // Compress responses
  compress: true,

  // Production source maps (disable for extra security)
  productionBrowserSourceMaps: false,
};

export default nextConfig;
