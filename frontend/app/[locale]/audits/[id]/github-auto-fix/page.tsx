import GitHubAutoFixPageClient from "./GitHubAutoFixPageClient";
import { requireServerViewer, serverJson } from "@/lib/server-api";

export default async function GitHubAutoFixPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;

  await requireServerViewer(`/${locale}/audits/${id}/github-auto-fix`);

  const [audit, connections] = await Promise.all([
    serverJson(`/api/v1/audits/${id}`).catch(() => null),
    serverJson<any[]>("/api/v1/github/connections").catch(() => []),
  ]);

  return (
    <GitHubAutoFixPageClient
      auditId={id}
      locale={locale}
      initialAudit={audit}
      initialConnections={connections}
      hasInitialConnections={Array.isArray(connections)}
    />
  );
}
