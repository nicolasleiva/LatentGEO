import { NextRequest, NextResponse } from "next/server";

import { auth0 } from "@/lib/auth0";
import { resolveApiBaseUrl } from "@/lib/env";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: {
    auditId: string;
  };
};

export async function GET(request: NextRequest, context: RouteContext) {
  const session = await auth0.getSession(request);
  if (!session?.user) {
    return NextResponse.json(
      { error: "Unauthorized: missing Auth0 session for SSE proxy" },
      { status: 401 },
    );
  }

  let accessToken: string;
  try {
    const audience =
      process.env.AUTH0_API_AUDIENCE?.trim() ||
      process.env.NEXT_PUBLIC_AUTH0_API_AUDIENCE?.trim() ||
      "";
    const scope =
      process.env.AUTH0_API_SCOPES?.trim() ||
      process.env.NEXT_PUBLIC_AUTH0_API_SCOPES?.trim() ||
      "read:app";

    if (!audience) {
      return NextResponse.json(
        { error: "Server misconfigured: AUTH0_API_AUDIENCE is missing for SSE proxy" },
        { status: 500 },
      );
    }

    const tokenResponse = await auth0.getAccessToken({
      refresh: false,
      audience,
      scope,
      authorizationParameters: {
        audience,
        scope,
      },
    });
    accessToken = tokenResponse.token;
  } catch {
    return NextResponse.json(
      { error: "Unauthorized: missing Auth0 access token for SSE proxy" },
      { status: 401 },
    );
  }

  const backendBaseUrl = resolveApiBaseUrl();
  const upstreamUrl = new URL(
    `/api/v1/sse/audits/${encodeURIComponent(context.params.auditId)}/progress`,
    backendBaseUrl,
  );

  try {
    const upstreamResponse = await fetch(upstreamUrl.toString(), {
      method: "GET",
      headers: {
        Authorization: `Bearer ${accessToken}`,
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
