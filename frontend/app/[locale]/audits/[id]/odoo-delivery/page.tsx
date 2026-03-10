import OdooDeliveryPageClient, {
  type OdooConnectionItem,
  type OdooDraftsPayload,
  type OdooSyncSummary,
  type PlanPayload,
} from "./OdooDeliveryPageClient";
import { requireServerViewer, serverJson } from "@/lib/server-api";

type OdooSyncResponse = {
  summary: OdooSyncSummary;
};

export default async function OdooDeliveryPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;

  await requireServerViewer(`/${locale}/audits/${id}/odoo-delivery`);

  const [audit, planResult, connectionsResult] = await Promise.all([
    serverJson(`/api/v1/audits/${id}`).catch(() => null),
    serverJson<PlanPayload>(`/api/v1/odoo/delivery-plan/${id}`)
      .then((payload) => ({ payload, error: null }))
      .catch((error) => ({
        payload: null,
        error: error instanceof Error ? error.message : "Unable to load plan.",
      })),
    serverJson<OdooConnectionItem[]>(`/api/v1/odoo/connections`)
      .then((payload) => ({ payload, error: null }))
      .catch(() => ({ payload: [], error: null })),
  ]);

  const hasConnection = Boolean(planResult.payload?.selected_connection?.id);
  const [syncResult, draftsResult] = hasConnection
    ? await Promise.all([
        serverJson<OdooSyncResponse>(`/api/v1/odoo/sync/${id}`)
          .then((payload) => ({ payload, error: null }))
          .catch(() => ({ payload: null, error: null })),
        serverJson<OdooDraftsPayload>(`/api/v1/odoo/drafts/${id}`)
          .then((payload) => ({ payload, error: null }))
          .catch(() => ({ payload: null, error: null })),
      ])
    : [{ payload: null, error: null }, { payload: null, error: null }];

  return (
    <OdooDeliveryPageClient
      auditId={id}
      locale={locale}
      initialAudit={audit}
      initialPlan={planResult.payload}
      initialConnections={connectionsResult.payload}
      initialSyncSummary={syncResult.payload?.summary || planResult.payload?.sync_summary}
      initialDrafts={draftsResult.payload}
      initialError={planResult.error}
    />
  );
}
