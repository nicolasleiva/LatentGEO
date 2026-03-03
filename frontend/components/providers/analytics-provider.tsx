import { Analytics as VercelAnalytics } from "@vercel/analytics/next";
import { env } from "@/lib/env";

export function AnalyticsProvider() {
  const provider = env.NEXT_PUBLIC_ANALYTICS_PROVIDER;
  const hostname =
    typeof window !== "undefined" ? window.location.hostname : "";
  const isLocalAuditHost =
    hostname === "localhost" || hostname === "127.0.0.1";

  if (isLocalAuditHost) {
    return null;
  }
  if (provider !== "vercel") {
    return null;
  }
  return <VercelAnalytics />;
}
