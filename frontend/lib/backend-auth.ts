import { getAccessToken } from "@auth0/nextjs-auth0/client";

import { resolveApiBaseUrl } from "./env";

const BACKEND_API_URL = resolveApiBaseUrl();
const REAUTH_REDIRECT_STORAGE_KEY = "reauth_redirect_at";
const REAUTH_REDIRECT_COOLDOWN_MS = 5_000;
const TOKEN_REFRESH_LOCK_STORAGE_KEY = "backend-auth-token-refresh-lock";
const TOKEN_BROADCAST_CHANNEL = "backend-auth-token";
const PEER_TOKEN_WAIT_MS = 1_200;

const AUTH0_API_AUDIENCE =
  process.env.NEXT_PUBLIC_AUTH0_API_AUDIENCE?.trim() || "";
const AUTH0_API_SCOPES =
  process.env.NEXT_PUBLIC_AUTH0_API_SCOPES?.trim() || "read:app";
let audienceMissingLogged = false;

let auth0AccessTokenCache: { token: string; expiresAtMs: number } | null = null;
const TOKEN_EXPIRY_SAFETY_MS = 5_000;

const shouldAttachBackendAuth = (requestUrl: URL) => {
  try {
    const backendOrigin = new URL(BACKEND_API_URL).origin;
    return (
      requestUrl.origin === backendOrigin ||
      requestUrl.href.startsWith(BACKEND_API_URL)
    );
  } catch {
    return false;
  }
};

const shouldRedirectToLogin = () => {
  if (typeof window === "undefined") return false;
  const path = window.location.pathname || "/";
  return !path.startsWith("/auth/") && !path.startsWith("/signin");
};

const canTriggerReauthRedirect = () => {
  if (typeof window === "undefined") return false;
  const rawTs = window.sessionStorage.getItem(REAUTH_REDIRECT_STORAGE_KEY) || "0";
  const lastTs = Number(rawTs);
  const now = Date.now();
  if (Number.isFinite(lastTs) && now - lastTs < REAUTH_REDIRECT_COOLDOWN_MS) {
    return false;
  }
  window.sessionStorage.setItem(REAUTH_REDIRECT_STORAGE_KEY, String(now));
  return true;
};

const redirectToLogin = () => {
  if (typeof window === "undefined") return;
  if (!shouldRedirectToLogin()) return;
  if (!canTriggerReauthRedirect()) return;

  const returnTo = `${window.location.pathname}${window.location.search}`;
  window.location.href = `/auth/login?returnTo=${encodeURIComponent(returnTo)}`;
};

const hasActiveAuth0Session = async (): Promise<boolean> => {
  try {
    const response = await fetch("/auth/profile", {
      method: "GET",
      credentials: "include",
      cache: "no-store",
    });
    return response.ok;
  } catch {
    return false;
  }
};

const getActiveRefreshLock = () => {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(TOKEN_REFRESH_LOCK_STORAGE_KEY);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as { expires_at?: number };
    const expiresAt = Number(parsed?.expires_at);
    if (!Number.isFinite(expiresAt) || expiresAt <= Date.now()) {
      return null;
    }
    return { expiresAt };
  } catch {
    return null;
  }
};

const waitForBroadcastedToken = async (): Promise<string | null> => {
  if (typeof window === "undefined" || typeof BroadcastChannel === "undefined") {
    return null;
  }

  return new Promise((resolve) => {
    const channel = new BroadcastChannel(TOKEN_BROADCAST_CHANNEL);
    const timeoutId = window.setTimeout(() => {
      channel.close();
      resolve(null);
    }, PEER_TOKEN_WAIT_MS);

    channel.onmessage = (event: MessageEvent) => {
      const payload = event?.data as
        | { type?: string; token?: string; expiry?: number }
        | undefined;
      if (payload?.type !== "token_refreshed" || !payload.token) {
        return;
      }

      const expiry = Number(payload.expiry);
      auth0AccessTokenCache = {
        token: payload.token,
        expiresAtMs: Number.isFinite(expiry) ? expiry : Date.now() + 50_000,
      };
      window.clearTimeout(timeoutId);
      channel.close();
      resolve(payload.token);
    };
  });
};

const broadcastTokenRefresh = (token: string, expiresAtMs: number) => {
  if (typeof window === "undefined" || typeof BroadcastChannel === "undefined") {
    return;
  }

  const channel = new BroadcastChannel(TOKEN_BROADCAST_CHANNEL);
  channel.postMessage({
    type: "token_refreshed",
    token,
    expiry: expiresAtMs,
  });
  channel.close();
};

export const getBackendAccessToken = async (
  forceRefresh = false,
): Promise<string | null> => {
  if (
    !forceRefresh &&
    auth0AccessTokenCache &&
    auth0AccessTokenCache.expiresAtMs > Date.now() + TOKEN_EXPIRY_SAFETY_MS
  ) {
    return auth0AccessTokenCache.token;
  }

  if (!forceRefresh && getActiveRefreshLock()) {
    const sharedToken = await waitForBroadcastedToken();
    if (sharedToken) {
      return sharedToken;
    }
  }

  try {
    if (!AUTH0_API_AUDIENCE) {
      if (!audienceMissingLogged) {
        console.error(
          "Missing NEXT_PUBLIC_AUTH0_API_AUDIENCE. Cannot request API access token.",
        );
        audienceMissingLogged = true;
      }
      return null;
    }

    const token = await getAccessToken({
      audience: AUTH0_API_AUDIENCE,
      scope: AUTH0_API_SCOPES,
    });

    if (!token) {
      auth0AccessTokenCache = null;
      return null;
    }

    auth0AccessTokenCache = {
      token,
      // Access token helper does not expose expiry in browser; keep a short cache.
      expiresAtMs: Date.now() + 50_000,
    };
    broadcastTokenRefresh(token, auth0AccessTokenCache.expiresAtMs);

    return token;
  } catch (error) {
    console.error("Error getting Auth0 access token:", error);
    auth0AccessTokenCache = null;
    return null;
  }
};

const clearBackendTokenCache = () => {
  auth0AccessTokenCache = null;
};

export const fetchWithBackendAuth = async (
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> => {
  if (typeof window === "undefined") {
    return fetch(input, init);
  }

  const requestUrl =
    input instanceof Request
      ? new URL(input.url)
      : new URL(input.toString(), window.location.origin);

  if (!shouldAttachBackendAuth(requestUrl)) {
    return fetch(input, init);
  }

  let token = await getBackendAccessToken();

  const headers = new Headers(init?.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response = await fetch(input, { ...init, headers });

  // Retry one time with forced token refresh on 401.
  if (response.status === 401) {
    token = await getBackendAccessToken(true);
    const retryHeaders = new Headers(init?.headers);
    if (token) {
      retryHeaders.set("Authorization", `Bearer ${token}`);
    }

    response = await fetch(input, { ...init, headers: retryHeaders });

    if (response.status === 401) {
      // Redirect only if Auth0 session is actually missing/expired.
      const sessionActive = await hasActiveAuth0Session();
      if (!sessionActive) {
        redirectToLogin();
      }
    }
  }

  return response;
};
