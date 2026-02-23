import { resolveApiBaseUrl } from "./env";

type BackendTokenResponse = {
  token?: string;
  access_token?: string;
  expires_at?: number;
};

type BackendTokenBroadcastMessage =
  | {
      type: "token_refreshed";
      token: string;
      expiry: number;
    }
  | {
      type: "token_cleared";
    };

type RefreshLockPayload = {
  owner: string;
  expires_at: number;
};

let cachedToken: string | null = null;
let cachedExpiry = 0;
let pendingTokenRequest: Promise<string | null> | null = null;
let tokenChannel: BroadcastChannel | null = null;

const tokenWaiters = new Set<(token: string | null) => void>();

const TOKEN_CHANNEL_NAME = "backend-auth-token";
const TOKEN_REFRESH_LOCK_KEY = "backend-auth-token-refresh-lock";
const TOKEN_REFRESH_LOCK_TTL_MS = 10_000;
const TOKEN_BROADCAST_WAIT_MS = 1_500;
const TOKEN_LOCK_POLL_MS = 150;
const TAB_ID = `tab-${Math.random().toString(36).slice(2)}`;

const BACKEND_API_URL = resolveApiBaseUrl();

const isBrowser = () => typeof window !== "undefined";

const isTokenFresh = () => {
  if (!cachedToken) return false;
  // Refresh one minute before expiry.
  return Date.now() < cachedExpiry - 60_000;
};

const notifyTokenWaiters = (token: string | null) => {
  tokenWaiters.forEach((resolveWaiter) => resolveWaiter(token));
  tokenWaiters.clear();
};

const ensureTokenChannel = () => {
  if (!isBrowser() || typeof BroadcastChannel === "undefined") {
    return null;
  }
  if (tokenChannel) {
    return tokenChannel;
  }

  tokenChannel = new BroadcastChannel(TOKEN_CHANNEL_NAME);
  tokenChannel.onmessage = (event: MessageEvent<BackendTokenBroadcastMessage>) => {
    const message = event.data;
    if (!message || typeof message !== "object") {
      return;
    }

    if (message.type === "token_refreshed") {
      cachedToken = message.token;
      cachedExpiry = Number(message.expiry || 0);
      notifyTokenWaiters(cachedToken);
      return;
    }

    if (message.type === "token_cleared") {
      resetBackendTokenCache(false);
    }
  };

  return tokenChannel;
};

const broadcastTokenMessage = (message: BackendTokenBroadcastMessage) => {
  const channel = ensureTokenChannel();
  if (channel) {
    channel.postMessage(message);
  }
};

const parseRefreshLock = (raw: string | null): RefreshLockPayload | null => {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as RefreshLockPayload;
    if (
      !parsed ||
      typeof parsed.owner !== "string" ||
      typeof parsed.expires_at !== "number"
    ) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
};

const tryAcquireRefreshLock = () => {
  if (!isBrowser()) return true;

  try {
    const now = Date.now();
    const current = parseRefreshLock(
      window.localStorage.getItem(TOKEN_REFRESH_LOCK_KEY),
    );
    if (current && current.expires_at > now && current.owner !== TAB_ID) {
      return false;
    }

    const nextLock: RefreshLockPayload = {
      owner: TAB_ID,
      expires_at: now + TOKEN_REFRESH_LOCK_TTL_MS,
    };
    window.localStorage.setItem(TOKEN_REFRESH_LOCK_KEY, JSON.stringify(nextLock));
    return true;
  } catch {
    return true;
  }
};

const releaseRefreshLock = () => {
  if (!isBrowser()) return;

  try {
    const current = parseRefreshLock(
      window.localStorage.getItem(TOKEN_REFRESH_LOCK_KEY),
    );
    if (current?.owner === TAB_ID) {
      window.localStorage.removeItem(TOKEN_REFRESH_LOCK_KEY);
    }
  } catch {
    // noop
  }
};

const waitForTokenBroadcast = async (timeoutMs: number): Promise<string | null> => {
  if (!isBrowser() || typeof BroadcastChannel === "undefined") {
    return null;
  }

  ensureTokenChannel();

  return new Promise<string | null>((resolve) => {
    const waiter = (token: string | null) => {
      clearTimeout(timer);
      tokenWaiters.delete(waiter);
      resolve(token);
    };

    const timer = window.setTimeout(() => {
      tokenWaiters.delete(waiter);
      resolve(null);
    }, timeoutMs);

    tokenWaiters.add(waiter);
  });
};

const waitForRefreshLockRelease = async (timeoutMs: number) => {
  if (!isBrowser()) return;

  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const current = parseRefreshLock(
      window.localStorage.getItem(TOKEN_REFRESH_LOCK_KEY),
    );
    if (!current || current.expires_at <= Date.now()) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, TOKEN_LOCK_POLL_MS));
  }
};

const resetBackendTokenCache = (broadcast = true) => {
  cachedToken = null;
  cachedExpiry = 0;
  pendingTokenRequest = null;
  notifyTokenWaiters(null);

  if (broadcast) {
    broadcastTokenMessage({ type: "token_cleared" });
  }
};

export const clearBackendTokenCache = () => {
  resetBackendTokenCache(true);
};

export const getBackendAccessToken = async (
  forceRefresh = false,
): Promise<string | null> => {
  if (!forceRefresh && isTokenFresh()) {
    return cachedToken;
  }

  if (pendingTokenRequest) {
    return pendingTokenRequest;
  }

  ensureTokenChannel();

  pendingTokenRequest = (async () => {
    let lockAcquired = false;
    try {
      lockAcquired = tryAcquireRefreshLock();
      if (!lockAcquired) {
        const broadcastToken = await waitForTokenBroadcast(TOKEN_BROADCAST_WAIT_MS);
        if (!forceRefresh && broadcastToken && isTokenFresh()) {
          return broadcastToken;
        }
        await waitForRefreshLockRelease(TOKEN_BROADCAST_WAIT_MS);
        lockAcquired = tryAcquireRefreshLock();
      }

      if (!forceRefresh && isTokenFresh()) {
        return cachedToken;
      }

      const res = await fetch("/api/auth/backend-token", {
        method: "GET",
        credentials: "include",
        headers: { Accept: "application/json" },
      });
      if (!res.ok) {
        resetBackendTokenCache(true);
        return null;
      }

      const payload = (await res.json()) as BackendTokenResponse;
      const token = payload.token || payload.access_token || null;
      if (!token) {
        resetBackendTokenCache(true);
        return null;
      }

      cachedToken = token;
      cachedExpiry = Number(payload.expires_at || Date.now() + 5 * 60_000);
      broadcastTokenMessage({
        type: "token_refreshed",
        token: cachedToken,
        expiry: cachedExpiry,
      });
      notifyTokenWaiters(cachedToken);
      return cachedToken;
    } catch {
      resetBackendTokenCache(true);
      return null;
    } finally {
      if (lockAcquired) {
        releaseRefreshLock();
      }
      pendingTokenRequest = null;
    }
  })();

  return pendingTokenRequest;
};

const shouldAttachBackendAuth = (requestUrl: URL) => {
  const backendOrigin = new URL(BACKEND_API_URL).origin;
  return (
    requestUrl.origin === backendOrigin &&
    requestUrl.pathname.startsWith("/api/")
  );
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

  const token = await getBackendAccessToken();
  const baseRequest =
    input instanceof Request ? input : new Request(input, init);
  const headers = new Headers(baseRequest.headers);

  if (init?.headers) {
    const initHeaders = new Headers(init.headers);
    initHeaders.forEach((value, key) => headers.set(key, value));
  }

  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const credentials = init?.credentials ?? baseRequest.credentials ?? "include";

  const buildRequest = (authHeaders: Headers) =>
    new Request(baseRequest, {
      ...init,
      headers: authHeaders,
      credentials,
    });

  let response = await fetch(buildRequest(headers));

  // Token may be expired/rotated; refresh once and retry transparently.
  if (response.status === 401 && token) {
    clearBackendTokenCache();
    const refreshedToken = await getBackendAccessToken(true);
    if (refreshedToken) {
      const retryHeaders = new Headers(headers);
      retryHeaders.set("Authorization", `Bearer ${refreshedToken}`);
      response = await fetch(buildRequest(retryHeaders));
    }
  }

  return response;
};

