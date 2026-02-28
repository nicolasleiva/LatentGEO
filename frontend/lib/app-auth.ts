"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

export const SIGNIN_PATH = "/auth/login";
const REAUTH_REDIRECT_STORAGE_KEY = "reauth_redirect_at";
const REAUTH_REDIRECT_COOLDOWN_MS = 5_000;

export type Auth0UserSummary = {
  sub?: string;
  email?: string;
  name?: string;
  picture?: string;
};

type Auth0StatusResponse = {
  authenticated: boolean;
  user: Auth0UserSummary | null;
};

export type AppAuthState = {
  loading: boolean;
  // Legacy alias kept to avoid broad UI churn after dual-auth removal.
  supabase_ok: boolean;
  auth0_ok: boolean;
  ready: boolean;
  // Legacy slot kept for compatibility.
  supabase_user: null;
  auth0_user: Auth0UserSummary | null;
};

const emptyState: AppAuthState = {
  loading: true,
  supabase_ok: false,
  auth0_ok: false,
  ready: false,
  supabase_user: null,
  auth0_user: null,
};

const safeReturnTo = (returnTo?: string): string => {
  if (!returnTo) return "/";
  if (!returnTo.startsWith("/")) return "/";
  if (returnTo.startsWith("//")) return "/";
  return returnTo;
};

const inAuthRoute = (pathname: string) => pathname.startsWith("/auth/");
const inSigninRoute = (pathname: string) => pathname === "/signin" || pathname.startsWith("/signin/");

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

export const buildAuth0LoginUrl = (returnTo?: string): string => {
  const rt = safeReturnTo(returnTo);
  return `/auth/login?returnTo=${encodeURIComponent(rt)}`;
};

const fetchAuth0Status = async (): Promise<Auth0StatusResponse> => {
  // Primary source: Auth0 SDK profile endpoint.
  try {
    const response = await fetch("/auth/profile", {
      method: "GET",
      credentials: "include",
      cache: "no-store",
      headers: { Accept: "application/json" },
    });

    if (response.ok) {
      const payload = (await response.json()) as Partial<Auth0UserSummary>;
      return {
        authenticated: true,
        user: {
          sub: typeof payload.sub === "string" ? payload.sub : undefined,
          email: typeof payload.email === "string" ? payload.email : undefined,
          name: typeof payload.name === "string" ? payload.name : undefined,
          picture:
            typeof payload.picture === "string" ? payload.picture : undefined,
        },
      };
    }
  } catch {
    // Fallback below.
  }

  // Fallback: internal status endpoint
  try {
    const response = await fetch("/api/auth/status", {
      method: "GET",
      credentials: "include",
      cache: "no-store",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) return { authenticated: false, user: null };

    const payload = (await response.json()) as Partial<Auth0StatusResponse>;
    return {
      authenticated: payload.authenticated === true,
      user: payload.user ?? null,
    };
  } catch {
    return { authenticated: false, user: null };
  }
};

export const useAppAuthState = (): AppAuthState => {
  const [state, setState] = useState<AppAuthState>(emptyState);

  const refresh = useCallback(async () => {
    const auth0Result = await fetchAuth0Status();
    const authenticated = auth0Result.authenticated;

    setState({
      loading: false,
      supabase_ok: authenticated,
      auth0_ok: authenticated,
      ready: authenticated,
      supabase_user: null,
      auth0_user: auth0Result.user,
    });
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return state;
};

export const useRequireAppAuth = (signinPath = SIGNIN_PATH): AppAuthState => {
  const router = useRouter();
  const auth = useAppAuthState();

  useEffect(() => {
    if (auth.loading || auth.ready || typeof window === "undefined") return;

    const currentPath = `${window.location.pathname}${window.location.search}`;
    if (inAuthRoute(window.location.pathname) || inSigninRoute(window.location.pathname)) return;

    // Give session cookies a brief grace period after callback before redirecting.
    const timer = window.setTimeout(async () => {
      const status = await fetchAuth0Status();
      if (status.authenticated) {
        router.refresh();
        return;
      }

      if (!canTriggerReauthRedirect()) return;
      router.replace(buildAuth0LoginUrl(currentPath) || signinPath);
    }, 500);

    return () => window.clearTimeout(timer);
  }, [auth.loading, auth.ready, router, signinPath]);

  return auth;
};

export const useCombinedProfile = (auth: AppAuthState) => {
  return useMemo(() => {
    const user = auth.auth0_user;
    const email = user?.email || "";
    const name = user?.name || email || "User";
    const picture = user?.picture;
    const id = user?.sub || "";

    return { id, email, name, picture };
  }, [auth.auth0_user]);
};

export const logoutAllSessions = (returnTo = "/auth/login") => {
  if (typeof window !== "undefined") {
    window.location.href = `/auth/logout?returnTo=${encodeURIComponent(
      safeReturnTo(returnTo),
    )}`;
  }
};
