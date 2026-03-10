import "server-only";

import { cache } from "react";
import { redirect } from "next/navigation";

import { isAdminSessionUser } from "@/lib/admin";
import { auth0 } from "@/lib/auth0";
import { resolveApiBaseUrl } from "@/lib/env";

type SessionUser = Record<string, unknown> & {
  sub?: string;
  email?: string;
  name?: string;
  nickname?: string;
  picture?: string;
};

export type ServerViewer = {
  sub?: string;
  email?: string;
  name?: string;
  picture?: string;
  isAdmin: boolean;
};

const API_BASE_URL = resolveApiBaseUrl();
const AUTH0_API_AUDIENCE =
  process.env.AUTH0_API_AUDIENCE?.trim() ||
  process.env.NEXT_PUBLIC_AUTH0_API_AUDIENCE?.trim() ||
  "";
const AUTH0_API_SCOPE =
  process.env.AUTH0_API_SCOPES?.trim() ||
  process.env.NEXT_PUBLIC_AUTH0_API_SCOPES?.trim() ||
  "read:app";

const getServerSession = cache(async () => auth0.getSession());

export const getServerViewer = cache(async (): Promise<ServerViewer | null> => {
  const session = await getServerSession();
  const user = session?.user;
  if (!user || typeof user !== "object") {
    return null;
  }

  const sessionUser = user as SessionUser;
  return {
    sub: typeof sessionUser.sub === "string" ? sessionUser.sub : undefined,
    email:
      typeof sessionUser.email === "string" ? sessionUser.email : undefined,
    name:
      typeof sessionUser.name === "string"
        ? sessionUser.name
        : typeof sessionUser.nickname === "string"
          ? sessionUser.nickname
          : undefined,
    picture:
      typeof sessionUser.picture === "string" ? sessionUser.picture : undefined,
    isAdmin: isAdminSessionUser(sessionUser),
  };
});

const getServerAccessToken = cache(async (): Promise<string> => {
  if (!AUTH0_API_AUDIENCE) {
    throw new Error("Missing AUTH0_API_AUDIENCE for server-side API requests.");
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
    throw new Error("Missing Auth0 access token for server-side API requests.");
  }

  return tokenResponse.token;
});

export async function requireServerViewer(
  returnTo: string,
  options: { requireAdmin?: boolean; forbiddenTo?: string } = {},
): Promise<ServerViewer> {
  const viewer = await getServerViewer();
  if (!viewer) {
    redirect(`/auth/login?returnTo=${encodeURIComponent(returnTo)}`);
  }
  if (options.requireAdmin && !viewer.isAdmin) {
    redirect(options.forbiddenTo || "/en?forbidden=admin");
  }
  return viewer;
}

function buildHeaders(initHeaders: HeadersInit | undefined, token: string) {
  const headers = new Headers(initHeaders);
  headers.set("Authorization", `Bearer ${token}`);
  headers.set("Accept", "application/json");
  return headers;
}

async function buildApiError(response: Response): Promise<Error> {
  const fallback = `Backend request failed: ${response.status}`;
  try {
    const payload: unknown = await response.json();
    if (payload && typeof payload === "object") {
      const detail = (payload as { detail?: unknown }).detail;
      if (typeof detail === "string" && detail.trim()) {
        return new Error(detail);
      }
      const message = (payload as { message?: unknown }).message;
      if (typeof message === "string" && message.trim()) {
        return new Error(message);
      }
    }
  } catch {
    // Keep fallback below.
  }
  return new Error(fallback);
}

export async function serverFetch(pathname: string, init?: RequestInit) {
  const token = await getServerAccessToken();
  const url = new URL(pathname, API_BASE_URL);
  const response = await fetch(url, {
    ...init,
    cache: "no-store",
    headers: buildHeaders(init?.headers, token),
    next: { revalidate: 0, ...init?.next },
  });
  if (!response.ok) {
    throw await buildApiError(response);
  }
  return response;
}

export async function serverJson<T>(
  pathname: string,
  init?: RequestInit,
): Promise<T> {
  const response = await serverFetch(pathname, init);
  return (await response.json()) as T;
}
