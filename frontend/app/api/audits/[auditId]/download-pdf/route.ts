import { NextRequest } from "next/server";

import { proxyProtectedPdfDownload } from "@/lib/server-download-proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ auditId: string }> },
) {
  const { auditId } = await context.params;

  return proxyProtectedPdfDownload(
    request,
    `/api/v1/audits/${auditId}/download-pdf`,
    `audit_${auditId}_report.pdf`,
  );
}
