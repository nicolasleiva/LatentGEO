import LLMVisibilityPageClient from "./LLMVisibilityPageClient";
import { requireServerViewer, serverJson } from "@/lib/server-api";
import type { LLMVisibility } from "@/lib/types";

const getBrandName = (auditUrl: string | undefined) => {
  if (!auditUrl) return "";
  try {
    const hostname = new URL(auditUrl).hostname.replace(/^www\./, "");
    return hostname.split(".")[0] || hostname;
  } catch {
    return "";
  }
};

export default async function LLMVisibilityPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id: auditId } = await params;
  await requireServerViewer(`/${locale}/audits/${auditId}/llm-visibility`);

  const [results, audit] = await Promise.all([
    serverJson<LLMVisibility[]>(`/api/v1/llm-visibility/${auditId}`).catch(
      () => [],
    ),
    serverJson<{ url?: string }>(`/api/v1/audits/${auditId}/status`).catch(
      () => ({}),
    ),
  ]);

  return (
    <LLMVisibilityPageClient
      auditId={auditId}
      initialResults={results}
      initialBrandName={
        "url" in audit && typeof audit.url === "string"
          ? getBrandName(audit.url)
          : ""
      }
    />
  );
}
