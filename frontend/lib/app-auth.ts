"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

const SIGNIN_PATH = "/auth/login";
const REAUTH_REDIRECT_STORAGE_KEY = "reauth_redirect_at";
const REAUTH_REDIRECT_COOLDOWN_MS = 5_000;

type Auth0UserSummary = {
  sub?: string;
  email?: string;
  name?: string;
  picture?: string;
};

type Auth0StatusResponse = {
  authenticated: boolean;
  is_admin?: boolean;
  user: Auth0UserSummary | null;
};

type AppAuthState = {
  loading: boolean;
  authenticated: boolean;
  // Legacy alias kept to avoid broad UI churn after dual-auth removal.
  supabase_ok: boolean;
  auth0_ok: boolean;
  ready: boolean;
  is_admin: boolean;
  forbidden: boolean;
  // Legacy slot kept for compatibility.
  supabase_user: null;
  auth0_user: Auth0UserSummary | null;
};

const emptyState: AppAuthState = {
  loading: true,
  authenticated: false,
  supabase_ok: false,
  auth0_ok: false,
  ready: false,
  is_admin: false,
  forbidden: false,
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
const inSigninRoute = (pathname: string) =>
  pathname === "/signin" || pathname.startsWith("/signin/");

const canTriggerReauthRedirect = () => {
  if (typeof window === "undefined") return false;
  const rawTs =
    window.sessionStorage.getItem(REAUTH_REDIRECT_STORAGE_KEY) || "0";
  const lastTs = Number(rawTs);
  const now = Date.now();
  if (Number.isFinite(lastTs) && now - lastTs < REAUTH_REDIRECT_COOLDOWN_MS) {
    return false;
  }
  window.sessionStorage.setItem(REAUTH_REDIRECT_STORAGE_KEY, String(now));
  return true;
};

const buildAuth0LoginUrl = (returnTo?: string): string => {
  const rt = safeReturnTo(returnTo);
  return `/auth/login?returnTo=${encodeURIComponent(rt)}`;
};

const fetchAuth0Status = async (): Promise<Auth0StatusResponse> => {
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
      is_admin: payload.is_admin === true,
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
      authenticated,
      supabase_ok: authenticated,
      auth0_ok: authenticated,
      ready: authenticated,
      is_admin: auth0Result.is_admin === true,
      forbidden: false,
      supabase_user: null,
      auth0_user: auth0Result.user,
    });
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return state;
};

export const useRequireAppAuth = ({
  signinPath = SIGNIN_PATH,
  requireAdmin = false,
}: {
  signinPath?: string;
  requireAdmin?: boolean;
} = {}): AppAuthState => {
  const router = useRouter();
  const auth = useAppAuthState();

  const guardedAuth = useMemo(
    () => ({
      ...auth,
      forbidden: requireAdmin && auth.authenticated && !auth.is_admin,
    }),
    [auth, requireAdmin],
  );

  useEffect(() => {
    if (auth.loading || auth.ready || typeof window === "undefined") return;

    const currentPath = `${window.location.pathname}${window.location.search}`;
    if (
      inAuthRoute(window.location.pathname) ||
      inSigninRoute(window.location.pathname)
    )
      return;

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

  return guardedAuth;
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
