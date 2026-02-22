import { z } from "zod";

const analyticsProviderSchema = z.enum(["vercel", "none"]);

const fallbackApiUrl =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  "http://localhost:8000";

const publicEnvSchema = z.object({
  NEXT_PUBLIC_API_URL: z.string().min(1),
  NEXT_PUBLIC_BACKEND_URL: z.string().min(1),
  NEXT_PUBLIC_ANALYTICS_PROVIDER: analyticsProviderSchema,
});

const publicEnv = publicEnvSchema.parse({
  NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || fallbackApiUrl,
  NEXT_PUBLIC_BACKEND_URL:
    process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || fallbackApiUrl,
  NEXT_PUBLIC_ANALYTICS_PROVIDER:
    (process.env.NEXT_PUBLIC_ANALYTICS_PROVIDER || "vercel").toLowerCase(),
});

export const env = publicEnv;

export function resolveApiBaseUrl(): string {
  const serverUrl = process.env.API_URL || env.NEXT_PUBLIC_API_URL;
  const selected = typeof window !== "undefined" ? env.NEXT_PUBLIC_API_URL : serverUrl;
  if (!selected) {
    throw new Error(
      "API URL is not configured. Set NEXT_PUBLIC_API_URL (browser) and API_URL (server).",
    );
  }
  return selected.replace(/\/+$/, "");
}

