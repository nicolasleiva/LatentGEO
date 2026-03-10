import ReportsExportsPageClient, {
  type ExportAudit,
} from "./ReportsExportsPageClient";
import { requireServerViewer, serverJson } from "@/lib/server-api";

export default async function ReportsExportsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  await requireServerViewer(`/${locale}/exports`);

  const completedAudits = await serverJson<ExportAudit[]>(
    "/api/v1/audits/status/completed",
  ).catch(() => []);

  return (
    <ReportsExportsPageClient locale={locale} initialAudits={completedAudits} />
  );
}
