import { NextRequest, NextResponse } from "next/server";

import { resolveApiBaseUrl } from "@/lib/env";
import { getServerProxyAccessToken } from "@/lib/server-proxy-auth";

const API_BASE_URL = resolveApiBaseUrl();

export async function proxyProtectedSse(
  request: NextRequest,
  backendPath: string,
): Promise<Response> {
  let accessToken: string;
  try {
    accessToken = await getServerProxyAccessToken(request);
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
  let streamOwnsCleanup = false;
  let cleanedUp = false;

  const cleanupAbortForwarding = () => {
    if (cleanedUp) {
      return;
    }
    cleanedUp = true;
    request.signal.removeEventListener("abort", abortUpstream);
  };

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
    streamOwnsCleanup = true;
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
            upstreamAbortController.abort();
            try {
              reader.releaseLock();
            } catch {
              // Ignore release errors after cancellation.
            }
            cleanupAbortForwarding();
          }
        };
        void pump();
      },
      cancel() {
        upstreamAbortController.abort();
        cleanupAbortForwarding();
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
    if (!streamOwnsCleanup) {
      cleanupAbortForwarding();
    }
  }
}
