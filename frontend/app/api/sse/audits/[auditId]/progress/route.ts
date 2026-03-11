import { NextRequest } from "next/server";

import { proxyProtectedSse } from "@/lib/server-sse-proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ auditId: string }> },
) {
  const { auditId } = await context.params;
  return proxyProtectedSse(
    request,
    `/api/v1/sse/audits/${encodeURIComponent(auditId)}/progress`,
  );
}
