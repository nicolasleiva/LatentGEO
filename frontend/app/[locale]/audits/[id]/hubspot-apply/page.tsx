import HubSpotApplyRecommendations from "@/components/hubspot-apply-recommendations";
import { requireServerViewer, serverJson } from "@/lib/server-api";

export default async function HubSpotApplyPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;

  await requireServerViewer(`/${locale}/audits/${id}/hubspot-apply`);

  const recommendationsResult = await serverJson<{ recommendations?: any[] }>(
    `/api/v1/hubspot/recommendations/${id}`,
  )
    .then((data) => ({
      recommendations: Array.isArray(data?.recommendations)
        ? data.recommendations
        : [],
      loaded: true,
    }))
    .catch(() => ({ recommendations: [] as any[], loaded: false }));

  return (
    <div className="container mx-auto py-8">
      <HubSpotApplyRecommendations
        auditId={id}
        initialRecommendations={recommendationsResult.recommendations}
        initialRecommendationsLoaded={recommendationsResult.loaded}
      />
    </div>
  );
}
