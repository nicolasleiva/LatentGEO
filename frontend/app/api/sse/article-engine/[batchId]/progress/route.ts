import { NextRequest, NextResponse } from "next/server";

import { proxyProtectedSse } from "@/lib/server-sse-proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ batchId: string }> },
) {
  const { batchId } = await context.params;
  if (!/^\d+$/.test(batchId)) {
    return NextResponse.json({ detail: "Invalid batch id" }, { status: 400 });
  }
  return proxyProtectedSse(
    request,
    `/api/v1/sse/article-engine/${encodeURIComponent(batchId)}/progress`,
  );
}
