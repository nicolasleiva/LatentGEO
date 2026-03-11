import RankTrackingPageClient from "./RankTrackingPageClient";
import { requireServerViewer } from "@/lib/server-api";

export default async function RankTrackingPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id: auditId } = await params;
  await requireServerViewer(`/${locale}/audits/${auditId}/rank-tracking`);

  return <RankTrackingPageClient auditId={auditId} />;
}
