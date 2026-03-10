import AnalyticsPageClient from "./AnalyticsPageClient";
import { requireServerViewer, serverJson } from "@/lib/server-api";

export default async function AnalyticsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  await requireServerViewer(`/${locale}/analytics`);
  const dashboardData = await serverJson("/api/v1/analytics/dashboard").catch(
    () => null,
  );
  return <AnalyticsPageClient locale={locale} dashboardData={dashboardData} />;
}
