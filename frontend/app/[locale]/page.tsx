import HomePageClient, { type HomeAudit } from "./HomePageClient";
import { requireServerViewer, serverJson } from "@/lib/server-api";

export default async function HomePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const returnTo = `/${locale}`;

  const [viewer, audits] = await Promise.all([
    requireServerViewer(returnTo),
    serverJson<HomeAudit[]>("/api/v1/audits/").catch(() => []),
  ]);

  const recentAudits = [...audits]
    .sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    )
    .slice(0, 6);

  return (
    <HomePageClient
      initialAudits={recentAudits}
      locale={locale}
      viewer={{
        id: viewer.sub,
        email: viewer.email,
        name: viewer.name,
        picture: viewer.picture || null,
      }}
    />
  );
}
