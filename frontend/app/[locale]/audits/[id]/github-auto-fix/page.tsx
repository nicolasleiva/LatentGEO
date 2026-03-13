import GitHubAutoFixPageClient from "./GitHubAutoFixPageClient";
import { requireServerViewer, serverJson } from "@/lib/server-api";

export default async function GitHubAutoFixPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;

  await requireServerViewer(`/${locale}/audits/${id}/github-auto-fix`);

  const [audit, connectionsResult] = await Promise.all([
    serverJson(`/api/v1/audits/${id}/summary`).catch(() => null),
    serverJson<any[]>("/api/v1/github/connections")
      .then((data) => ({
        data: Array.isArray(data) ? data : [],
        loaded: true,
      }))
      .catch(() => ({ data: [] as any[], loaded: false })),
  ]);

  return (
    <GitHubAutoFixPageClient
      auditId={id}
      locale={locale}
      initialAudit={audit}
      initialConnections={connectionsResult.data}
      hasInitialConnections={connectionsResult.loaded}
    />
  );
}
