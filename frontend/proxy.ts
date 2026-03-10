import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { isAdminOnlyPath, isAdminSessionUser } from "./lib/admin";
import { auth0 } from "./lib/auth0";

// EN-first strategy
const activeLocales = ["en"];
const legacyLocales = ["es"];
const defaultLocale = "en";

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 1. Handle Auth0 authentication routes
  if (pathname.startsWith("/auth/")) {
    try {
      return await auth0.middleware(request);
    } catch (error) {
      console.error("Auth0 middleware error:", error);
      if (pathname === "/auth/login") {
        return NextResponse.json(
          { error: "Auth middleware failed on /auth/login" },
          { status: 500 },
        );
      }

      const loginUrl = request.nextUrl.clone();
      loginUrl.pathname = "/auth/login";
      loginUrl.search = "";
      const returnTo = pathname.startsWith("/auth/")
        ? "/"
        : `${pathname}${request.nextUrl.search || ""}`;
      if (returnTo.startsWith("/") && !returnTo.startsWith("//")) {
        loginUrl.searchParams.set("returnTo", returnTo);
      }
      return NextResponse.redirect(loginUrl, 302);
    }
  }

  // Keep /signin outside locale prefixes to avoid auth redirect loops.
  if (pathname === "/signin" || pathname.startsWith("/signin/")) {
    return NextResponse.next();
  }

  if (
    pathname === "/integrations/github/callback" ||
    pathname.startsWith("/integrations/github/callback/")
  ) {
    return NextResponse.next();
  }

  // 2. Skip middleware for static files and internal paths
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname.startsWith("/locales") ||
    pathname.startsWith("/images") ||
    pathname.startsWith("/fonts") ||
    pathname.includes(".")
  ) {
    return NextResponse.next();
  }

  if (isAdminOnlyPath(pathname)) {
    try {
      const session = await auth0.getSession(request);
      if (!session?.user) {
        const loginUrl = request.nextUrl.clone();
        loginUrl.pathname = "/auth/login";
        loginUrl.search = "";
        loginUrl.searchParams.set(
          "returnTo",
          `${pathname}${request.nextUrl.search || ""}`,
        );
        return NextResponse.redirect(loginUrl, 302);
      }

      const sessionUser =
        typeof session.user === "object"
          ? (session.user as Record<string, unknown>)
          : null;
      if (!isAdminSessionUser(sessionUser)) {
        const forbiddenUrl = request.nextUrl.clone();
        forbiddenUrl.pathname = `/${defaultLocale}`;
        forbiddenUrl.search = "";
        forbiddenUrl.searchParams.set("forbidden", "admin");
        return NextResponse.redirect(forbiddenUrl, 302);
      }
    } catch (error) {
      console.error("Admin route authorization failed:", error);
      return NextResponse.redirect(new URL("/auth/login", request.url), 302);
    }
  }

  // 3. Handle active locale directly
  const hasActiveLocale = activeLocales.some(
    (locale) => pathname.startsWith(`/${locale}/`) || pathname === `/${locale}`,
  );
  if (hasActiveLocale) {
    return NextResponse.next();
  }

  // 4. Redirect legacy locale segments to /en/*
  const legacyLocale = legacyLocales.find(
    (locale) => pathname.startsWith(`/${locale}/`) || pathname === `/${locale}`,
  );
  if (legacyLocale) {
    const url = request.nextUrl.clone();
    const rest = pathname.slice(`/${legacyLocale}`.length) || "/";
    url.pathname = `/${defaultLocale}${rest === "/" ? "" : rest}`;
    return NextResponse.redirect(url);
  }

  // 5. Redirect to default locale
  const url = request.nextUrl.clone();
  if (pathname === "/") {
    url.pathname = `/${defaultLocale}`;
  } else {
    url.pathname = `/${defaultLocale}${pathname}`;
  }
  return NextResponse.redirect(url);
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)",
  ],
};
