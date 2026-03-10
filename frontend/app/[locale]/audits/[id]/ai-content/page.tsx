import AIContentPageClient from "./AIContentPageClient";
import { requireServerViewer, serverJson } from "@/lib/server-api";
import type { AIContentSuggestion } from "@/lib/types";

const getInitialDomain = (url: string | undefined) => {
  if (!url) return "";
  try {
    return new URL(url).hostname;
  } catch {
    return "";
  }
};

export default async function AIContentPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id: auditId } = await params;
  await requireServerViewer(`/${locale}/audits/${auditId}/ai-content`);

  const [suggestions, audit] = await Promise.all([
    serverJson<AIContentSuggestion[]>(`/api/v1/ai-content/${auditId}`).catch(
      () => [],
    ),
    serverJson<{ url?: string }>(`/api/v1/audits/${auditId}/status`).catch(
      () => ({}),
    ),
  ]);

  const auditUrl =
    "url" in audit && typeof audit.url === "string" ? audit.url : "";

  return (
    <AIContentPageClient
      auditId={auditId}
      initialDomain={getInitialDomain(auditUrl)}
      initialSuggestions={suggestions}
    />
  );
}
