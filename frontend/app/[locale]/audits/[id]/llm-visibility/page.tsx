import LLMVisibilityPageClient from "./LLMVisibilityPageClient";
import { requireServerViewer } from "@/lib/server-api";

export default async function LLMVisibilityPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id: auditId } = await params;
  await requireServerViewer(`/${locale}/audits/${auditId}/llm-visibility`);

  return <LLMVisibilityPageClient auditId={auditId} />;
}
