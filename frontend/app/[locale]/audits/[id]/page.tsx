import AuditDetailPageClient from "./AuditDetailPageClient";
import { requireServerViewer, serverJson } from "@/lib/server-api";

type AuditOverview = {
  id: number;
  url: string;
  status: string;
  progress: number;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  geo_score?: number | null;
  total_pages?: number | null;
  critical_issues?: number | null;
  high_issues?: number | null;
  medium_issues?: number | null;
  source?: string | null;
  language?: string | null;
  category?: string | null;
  market?: string | null;
  intake_profile?: {
    add_articles?: boolean;
    article_count?: number;
    improve_ecommerce_fixes?: boolean;
  } | null;
  diagnostics_summary?: Array<Record<string, unknown>> | null;
  error_message?: string | null;
  competitor_count?: number;
  fix_plan_count?: number;
  report_ready?: boolean;
  pagespeed_available?: boolean;
  pdf_available?: boolean;
  external_intelligence?: Record<string, unknown> | null;
};

export default async function AuditDetailPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;

  await requireServerViewer(`/${locale}/audits/${id}`);

  const audit = await serverJson<AuditOverview>(
    `/api/v1/audits/${id}/overview`,
  ).catch(() => null);

  return (
    <AuditDetailPageClient
      auditId={id}
      locale={locale}
      initialAudit={audit}
      initialAuditIsOverview
    />
  );
}
