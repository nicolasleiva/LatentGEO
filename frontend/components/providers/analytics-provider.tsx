import { Analytics as VercelAnalytics } from "@vercel/analytics/next";
import { env } from "@/lib/env";

const provider = env.NEXT_PUBLIC_ANALYTICS_PROVIDER;

export function AnalyticsProvider() {
  if (provider !== "vercel") {
    return null;
  }
  return <VercelAnalytics />;
}
