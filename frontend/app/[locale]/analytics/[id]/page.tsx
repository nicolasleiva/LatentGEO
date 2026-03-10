import AuditAnalyticsPageClient from "./AuditAnalyticsPageClient";
import { requireServerViewer, serverJson } from "@/lib/server-api";

export default async function AuditAnalyticsPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;
  const auditId = Number.parseInt(id, 10);

  await requireServerViewer(`/${locale}/analytics/${id}`);

  const analytics = await serverJson(
    `/api/v1/analytics/audit/${auditId}`,
  ).catch(() => null);

  return (
    <AuditAnalyticsPageClient
      auditId={auditId}
      locale={locale}
      analytics={analytics}
    />
  );
}
