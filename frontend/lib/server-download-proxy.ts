import { NextRequest, NextResponse } from "next/server";

import { auth0 } from "@/lib/auth0";
import { resolveApiBaseUrl } from "@/lib/env";

const API_BASE_URL = resolveApiBaseUrl();
const API_BASE_ORIGIN = new URL(API_BASE_URL).origin;
const AUTH0_API_AUDIENCE =
  process.env.AUTH0_API_AUDIENCE?.trim() ||
  process.env.NEXT_PUBLIC_AUTH0_API_AUDIENCE?.trim() ||
  "";
const AUTH0_API_SCOPE =
  process.env.AUTH0_API_SCOPES?.trim() ||
  process.env.NEXT_PUBLIC_AUTH0_API_SCOPES?.trim() ||
  "read:app";

const PDF_ACCEPT_HEADER =
  "application/pdf, application/octet-stream;q=0.9, application/json;q=0.8, */*;q=0.7";
const DOWNLOAD_TIMEOUT_MS = 30_000;

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit,
  timeoutMs = DOWNLOAD_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timeoutId);
  }
}

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

async function readErrorMessage(response: Response): Promise<string> {
  const fallback = `Download request failed: ${response.status}`;
  let rawBody = "";

  try {
    rawBody = await response.text();
  } catch {
    return fallback;
  }

  if (!rawBody.trim()) {
    return fallback;
  }

  try {
    const payload: unknown = JSON.parse(rawBody);
    if (payload && typeof payload === "object") {
      const detail = (payload as { detail?: unknown }).detail;
      if (typeof detail === "string" && detail.trim()) {
        return detail;
      }

      const error = (payload as { error?: unknown }).error;
      if (typeof error === "string" && error.trim()) {
        return error;
      }
    }
  } catch {
    return rawBody.trim();
  }

  return fallback;
}

function buildDownloadHeaders(
  upstream: Response,
  fallbackFilename: string,
): Headers {
  const headers = new Headers();
  headers.set("Cache-Control", "private, no-store");
  headers.set(
    "Content-Type",
    upstream.headers.get("content-type") || "application/pdf",
  );

  const upstreamDisposition = upstream.headers.get("content-disposition");
  headers.set(
    "Content-Disposition",
    upstreamDisposition && /attachment/i.test(upstreamDisposition)
      ? upstreamDisposition
      : `attachment; filename="${fallbackFilename}"`,
  );

  const contentLength = upstream.headers.get("content-length");
  if (contentLength) {
    headers.set("Content-Length", contentLength);
  }

  return headers;
}

async function streamPdfResponse(
  upstream: Response,
  fallbackFilename: string,
): Promise<NextResponse> {
  if (!upstream.body) {
    return NextResponse.json(
      { error: "Download stream is unavailable." },
      { status: 502 },
    );
  }

  return new NextResponse(upstream.body, {
    status: 200,
    headers: buildDownloadHeaders(upstream, fallbackFilename),
  });
}

export async function proxyProtectedPdfDownload(
  request: NextRequest,
  backendPath: string,
  fallbackFilename: string,
): Promise<NextResponse> {
  let token: string;
  try {
    token = await getBackendAccessToken(request);
  } catch (error) {
    const code = error instanceof Error ? error.message : "unauthorized";
    if (code === "missing_audience") {
      return NextResponse.json(
        { error: "Server misconfigured: AUTH0_API_AUDIENCE is missing" },
        { status: 500 },
      );
    }
    if (code === "unauthorized") {
      return NextResponse.json(
        { error: "Unauthorized: missing Auth0 session" },
        { status: 401 },
      );
    }
    return NextResponse.json(
      { error: "Unable to acquire backend access token." },
      { status: 502 },
    );
  }

  const backendUrl = new URL(backendPath, API_BASE_URL);
  if (backendUrl.origin !== API_BASE_ORIGIN) {
    return NextResponse.json(
      { error: "Unsafe backend download target." },
      { status: 500 },
    );
  }
  let backendResponse: Response;
  try {
    backendResponse = await fetchWithTimeout(backendUrl, {
      method: "GET",
      cache: "no-store",
      redirect: "manual",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: PDF_ACCEPT_HEADER,
      },
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      return NextResponse.json(
        { error: "Backend PDF download request timed out." },
        { status: 504 },
      );
    }
    throw error;
  }

  if (backendResponse.status >= 300 && backendResponse.status < 400) {
    const signedUrl = backendResponse.headers.get("location");
    if (!signedUrl) {
      return NextResponse.json(
        { error: "Download redirect is missing a signed URL." },
        { status: 502 },
      );
    }

    let upstreamResponse: Response;
    try {
      upstreamResponse = await fetchWithTimeout(signedUrl, {
        cache: "no-store",
        redirect: "follow",
      });
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") {
        return NextResponse.json(
          { error: "Signed PDF download timed out." },
          { status: 504 },
        );
      }
      throw error;
    }
    if (!upstreamResponse.ok) {
      return NextResponse.json(
        {
          error: `Signed download failed: ${upstreamResponse.status}`,
        },
        { status: 502 },
      );
    }

    return streamPdfResponse(upstreamResponse, fallbackFilename);
  }

  if (!backendResponse.ok) {
    return NextResponse.json(
      { error: await readErrorMessage(backendResponse) },
      { status: backendResponse.status },
    );
  }

  return streamPdfResponse(backendResponse, fallbackFilename);
}
