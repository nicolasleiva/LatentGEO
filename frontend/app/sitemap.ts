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

export default function sitemap(): MetadataRoute.Sitemap {
  const origin = resolveSiteOrigin();
  const now = new Date();

  return [
    {
      url: `${origin}/en/docs`,
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.8,
    },
    {
      url: `${origin}/en/pricing`,
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.9,
    },
  ];
}
