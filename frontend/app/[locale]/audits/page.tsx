import AuditsListPageClient, {
  type AuditsListItem,
} from "./AuditsListPageClient";
import { requireServerViewer, serverJson } from "@/lib/server-api";

export default async function AuditsListPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  await requireServerViewer(`/${locale}/audits`);
  const audits = await serverJson<AuditsListItem[]>("/api/v1/audits/").catch(
    () => [],
  );
  return <AuditsListPageClient initialAudits={audits} />;
}
