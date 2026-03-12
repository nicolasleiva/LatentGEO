import { NextRequest, NextResponse } from "next/server";

import { proxyProtectedSse } from "@/lib/server-sse-proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ auditId: string }> },
) {
  const { auditId } = await context.params;
  if (!/^\d+$/.test(auditId)) {
    return NextResponse.json({ detail: "Invalid audit id" }, { status: 400 });
  }
  return proxyProtectedSse(
    request,
    `/api/v1/sse/audits/${encodeURIComponent(auditId)}/progress`,
  );
}
