import createClient from "openapi-fetch";
import { fetchWithBackendAuth } from "@/lib/backend-auth";
import { resolveApiBaseUrl } from "@/lib/env";
import type { paths } from "./schema";

export const typedApiClient = createClient<paths>({
  baseUrl: resolveApiBaseUrl(),
  fetch: ((input: RequestInfo | URL, init?: RequestInit) =>
    fetchWithBackendAuth(input, init)) as typeof fetch,
});

export function ensureData<T>(
  payload: { data?: T; error?: unknown },
  fallback: string,
): T {
  if (payload.error) {
    const message =
      typeof payload.error === "object" && payload.error !== null
        ? JSON.stringify(payload.error)
        : String(payload.error);
    throw new Error(message || fallback);
  }
  if (payload.data === undefined) {
    throw new Error(fallback);
  }
  return payload.data;
}
