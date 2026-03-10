import RankTrackingPageClient from "./RankTrackingPageClient";
import { requireServerViewer, serverJson } from "@/lib/server-api";
import type { RankTracking } from "@/lib/types";

const getInitialRankConfig = (audit: Record<string, any>) => {
  const auditUrl = typeof audit.url === "string" ? audit.url : "";
  let hostname = "";
  try {
    hostname = auditUrl ? new URL(auditUrl).hostname : "";
  } catch {
    hostname = "";
  }

  const suggestedKeywords: string[] = [];
  if (hostname) {
    suggestedKeywords.push(hostname.replace(/^www\./, "").split(".")[0]);
  }
  if (typeof audit.category === "string" && audit.category.trim()) {
    suggestedKeywords.push(audit.category.toLowerCase());
  }
  const h1 = audit?.target_audit?.content?.h1;
  if (typeof h1 === "string" && h1.trim()) {
    suggestedKeywords.push(h1.toLowerCase());
  }

  return {
    domain: hostname,
    keywords: Array.from(new Set(suggestedKeywords)).slice(0, 5).join(", "),
  };
};

export default async function RankTrackingPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id: auditId } = await params;
  await requireServerViewer(`/${locale}/audits/${auditId}/rank-tracking`);

  const [rankings, audit] = await Promise.all([
    serverJson<RankTracking[]>(`/api/v1/rank-tracking/${auditId}`).catch(
      () => [],
    ),
    serverJson<Record<string, any>>(`/api/v1/audits/${auditId}`).catch(
      () => ({}),
    ),
  ]);

  const initialConfig = getInitialRankConfig(audit);

  return (
    <RankTrackingPageClient
      auditId={auditId}
      initialDomain={initialConfig.domain}
      initialKeywords={initialConfig.keywords}
      initialRankings={rankings}
    />
  );
}
