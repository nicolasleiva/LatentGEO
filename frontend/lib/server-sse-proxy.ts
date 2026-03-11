import { NextRequest, NextResponse } from "next/server";

import { auth0 } from "@/lib/auth0";
import { resolveApiBaseUrl } from "@/lib/env";

const API_BASE_URL = resolveApiBaseUrl();
const AUTH0_API_AUDIENCE =
  process.env.AUTH0_API_AUDIENCE?.trim() ||
  process.env.NEXT_PUBLIC_AUTH0_API_AUDIENCE?.trim() ||
  "";
const AUTH0_API_SCOPE =
  process.env.AUTH0_API_SCOPES?.trim() ||
  process.env.NEXT_PUBLIC_AUTH0_API_SCOPES?.trim() ||
  "read:app";

async function getBackendAccessToken(request: NextRequest): Promise<string> {
  const session = await auth0.getSession(request);
  if (!session?.user) {
    throw new Error("unauthorized");
  }

  if (!AUTH0_API_AUDIENCE) {
    throw new Error("missing_audience");
  }

  const tokenResponse = await auth0.getAccessToken({
    refresh: false,
    audience: AUTH0_API_AUDIENCE,
    scope: AUTH0_API_SCOPE,
    authorizationParameters: {
      audience: AUTH0_API_AUDIENCE,
      scope: AUTH0_API_SCOPE,
    },
  });

  if (!tokenResponse?.token) {
    throw new Error("missing_token");
  }

  return tokenResponse.token;
}

export async function proxyProtectedSse(
  request: NextRequest,
  backendPath: string,
): Promise<Response> {
  let accessToken: string;
  try {
    accessToken = await getBackendAccessToken(request);
  } catch (error) {
    const code = error instanceof Error ? error.message : "unauthorized";
    if (code === "missing_audience") {
      return NextResponse.json(
        {
          error:
            "Server misconfigured: AUTH0_API_AUDIENCE is missing for SSE proxy",
        },
        { status: 500 },
      );
    }

    return NextResponse.json(
      { error: "Unauthorized: missing Auth0 session for SSE proxy" },
      { status: 401 },
    );
  }

  const upstreamAbortController = new AbortController();
  const abortUpstream = () => upstreamAbortController.abort();
  request.signal.addEventListener("abort", abortUpstream, { once: true });

  try {
    const upstreamUrl = new URL(backendPath, API_BASE_URL);
    const upstreamResponse = await fetch(upstreamUrl.toString(), {
      method: "GET",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        Accept: "text/event-stream",
      },
      cache: "no-store",
      signal: upstreamAbortController.signal,
    });

    if (!upstreamResponse.ok) {
      const fallbackBody =
        (await upstreamResponse.text()) ||
        "Failed to establish SSE stream from backend";
      return NextResponse.json(
        {
          error: "SSE proxy upstream rejected request",
          status: upstreamResponse.status,
          detail: fallbackBody,
        },
        { status: upstreamResponse.status || 502 },
      );
    }

    if (!upstreamResponse.body) {
      return NextResponse.json(
        { error: "SSE proxy upstream body missing" },
        { status: 502 },
      );
    }

    const reader = upstreamResponse.body.getReader();
    const proxiedBody = new ReadableStream<Uint8Array>({
      start(controller) {
        const pump = async () => {
          try {
            while (true) {
              const { done, value } = await reader.read();
              if (done) {
                controller.close();
                break;
              }
              if (value) {
                controller.enqueue(value);
              }
            }
          } catch (streamError) {
            controller.error(streamError);
          } finally {
            reader.releaseLock();
          }
        };
        void pump();
      },
      cancel() {
        return reader.cancel();
      },
    });

    const headers = new Headers();
    headers.set(
      "Content-Type",
      upstreamResponse.headers.get("content-type") || "text/event-stream",
    );
    headers.set("Cache-Control", "no-cache, no-store, must-revalidate");
    headers.set("Connection", "keep-alive");
    headers.set("X-Accel-Buffering", "no");

    return new Response(proxiedBody, {
      status: 200,
      headers,
    });
  } catch (error) {
    const detail =
      error instanceof Error ? error.message : "Unknown SSE proxy error";
    return NextResponse.json(
      { error: "SSE proxy upstream error", detail },
      { status: 502 },
    );
  } finally {
    request.signal.removeEventListener("abort", abortUpstream);
  }
}
