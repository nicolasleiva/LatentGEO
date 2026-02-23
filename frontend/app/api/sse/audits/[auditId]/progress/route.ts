import { NextRequest, NextResponse } from "next/server";

import { auth0 } from "@/lib/auth0";
import { resolveApiBaseUrl } from "@/lib/env";
import { createBackendInternalToken } from "@/lib/internal-backend-jwt";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: {
    auditId: string;
  };
};

export async function GET(request: NextRequest, context: RouteContext) {
  const session = await auth0.getSession(request);
  const user = session?.user;
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const tokenData = createBackendInternalToken(user);
  if ("error" in tokenData) {
    const status = tokenData.error.startsWith("Invalid user session") ? 401 : 500;
    return NextResponse.json({ error: tokenData.error }, { status });
  }

  const backendBaseUrl = resolveApiBaseUrl();
  const upstreamUrl = new URL(
    `/api/sse/audits/${encodeURIComponent(context.params.auditId)}/progress`,
    backendBaseUrl,
  );

  try {
    const upstreamResponse = await fetch(upstreamUrl.toString(), {
      method: "GET",
      headers: {
        Authorization: `Bearer ${tokenData.token}`,
        Accept: "text/event-stream",
      },
      cache: "no-store",
    });

    if (!upstreamResponse.body) {
      const fallbackBody =
        (await upstreamResponse.text()) ||
        "Failed to establish SSE stream from backend";
      return new Response(fallbackBody, {
        status: upstreamResponse.status || 502,
      });
    }

    const headers = new Headers();
    headers.set(
      "Content-Type",
      upstreamResponse.headers.get("content-type") || "text/event-stream",
    );
    headers.set("Cache-Control", "no-cache, no-store, must-revalidate");
    headers.set("Connection", "keep-alive");
    headers.set("X-Accel-Buffering", "no");

    return new Response(upstreamResponse.body, {
      status: upstreamResponse.status,
      headers,
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : "Unknown SSE proxy error";
    return NextResponse.json(
      { error: "SSE proxy upstream error", detail },
      { status: 502 },
    );
  }
}

