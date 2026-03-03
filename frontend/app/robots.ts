import type { MetadataRoute } from "next";
import { APP_METADATA } from "@/lib/brand";

function resolveSiteOrigin(): string {
  const raw =
    process.env.NEXT_PUBLIC_SITE_URL?.trim() || APP_METADATA.siteUrl.trim();
  try {
    return new URL(raw).origin;
  } catch {
    return APP_METADATA.siteUrl;
  }
}

export default function robots(): MetadataRoute.Robots {
  const origin = resolveSiteOrigin();

  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/en/docs", "/en/pricing"],
        disallow: [
          "/api/",
          "/auth/",
          "/signin",
          "/en",
          "/en/analytics",
          "/en/audits",
          "/en/content-analysis",
          "/en/exports",
          "/en/integrations",
          "/en/ops",
          "/en/pagespeed",
          "/en/reports",
          "/en/settings",
          "/en/tools",
        ],
      },
    ],
    sitemap: `${origin}/sitemap.xml`,
    host: origin,
  };
}
