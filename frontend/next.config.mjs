import path from "node:path";
import { fileURLToPath } from "node:url";

/** @type {import('next').NextConfig} */
const isProd =
  process.env.NODE_ENV === "production" ||
  process.env.ENVIRONMENT === "production";
const strictBuild = process.env.STRICT_BUILD === "1";
const ciValidationBuild =
  process.env.CI === "true" || process.env.GITHUB_ACTIONS === "true";
const allowLocalhostApiOrigin =
  process.env.ALLOW_LOCALHOST_API_ORIGIN === "1" ||
  ciValidationBuild ||
  (!isProd && !strictBuild);
const configDir = path.dirname(fileURLToPath(import.meta.url));
const httpsEnforced = isProd && process.env.FORCE_HTTPS === "true";
const devFallbackApiUrl = "http://localhost:8000";
const localHostnames = new Set(["localhost", "127.0.0.1", "0.0.0.0"]);
const buildValidationFallbackApiUrl =
  ciValidationBuild || (!isProd && !strictBuild) ? devFallbackApiUrl : "";

function selectApiUrl(...candidates) {
  for (const candidate of candidates) {
    const trimmed = candidate?.trim();
    if (trimmed) {
      return trimmed;
    }
  }
  if (isProd) {
    return buildValidationFallbackApiUrl;
  }
  return devFallbackApiUrl;
}

function normalizeAbsoluteUrl(value, label) {
  if (!value) {
    return "";
  }

  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    throw new Error(`${label} must be an absolute URL`);
  }

  if (
    isProd &&
    !allowLocalhostApiOrigin &&
    localHostnames.has(parsed.hostname)
  ) {
    throw new Error(`${label} cannot target localhost in production`);
  }

  return parsed.toString().replace(/\/+$/, "");
}

const rawApiUrl = normalizeAbsoluteUrl(
  selectApiUrl(process.env.NEXT_PUBLIC_API_URL, process.env.API_URL),
  "NEXT_PUBLIC_API_URL/API_URL",
);
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

if (strictBuild && !apiOrigin) {
  throw new Error("Missing API origin for strict build.");
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
  outputFileTracingRoot: configDir,

  // Local builds can skip expensive checks. CI sets STRICT_BUILD=1.
  typescript: {
    ignoreBuildErrors: !strictBuild,
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
    formats: ["image/avif", "image/webp"],
  },

  // ===== PRODUCTION SECURITY HEADERS =====
  async headers() {
    const defaultHeaders = [
      {
        key: "X-Content-Type-Options",
        value: "nosniff",
      },
      {
        key: "X-Frame-Options",
        value: "DENY",
      },
      {
        key: "X-XSS-Protection",
        value: "1; mode=block",
      },
      {
        key: "Referrer-Policy",
        value: "strict-origin-when-cross-origin",
      },
      {
        key: "Permissions-Policy",
        value: "geolocation=(), microphone=(), camera=(), payment=()",
      },
      {
        key: "Content-Security-Policy",
        value: [
          "default-src 'self'",
          "script-src 'self' 'unsafe-inline' https://apis.google.com https://www.googletagmanager.com",
          "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
          "font-src 'self' https://fonts.gstatic.com data:",
          "img-src 'self' data: https: blob:",
          `connect-src ${connectSrc.join(" ")}`,
          "frame-ancestors 'none'",
          "form-action 'self'",
          "base-uri 'self'",
          "object-src 'none'",
          httpsEnforced ? "upgrade-insecure-requests" : "",
        ]
          .filter(Boolean)
          .join("; "),
      },
    ];

    if (httpsEnforced) {
      defaultHeaders.push({
        key: "Strict-Transport-Security",
        value: "max-age=31536000; includeSubDomains; preload",
      });
    }

    return [
      {
        source: "/:path*",
        headers: defaultHeaders,
      },
      {
        source: "/_next/static/:path*",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=31536000, immutable",
          },
        ],
      },
      {
        source: "/static/:path*",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=31536000, immutable",
          },
        ],
      },
      {
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
