import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { auth0 } from "./lib/auth0";

// Supported locales
const locales = ['en', 'es'];
const defaultLocale = 'en';

export async function middleware(request: NextRequest) {
    const { pathname } = request.nextUrl;

    // Debug logging (server-side)
    // console.log(`Middleware: ${pathname}`);

    // 1. Handle Auth0 authentication routes
    if (pathname.startsWith('/auth/')) {
        try {
            return await auth0.middleware(request);
        } catch (error) {
            console.error('Auth0 middleware error:', error);
            // Si hay error en Auth0, continuar sin autenticación
            return NextResponse.next();
        }
    }

    // 2. Skip middleware for static files and internal paths
    // The matcher in config already handles most of this, but we double check
    if (
        pathname.startsWith('/_next') ||
        pathname.startsWith('/api') ||
        pathname.startsWith('/locales') ||
        pathname.startsWith('/images') ||
        pathname.startsWith('/fonts') ||
        pathname.includes('.') // Crude check for files, better handled by matcher
    ) {
        return NextResponse.next();
    }

    // 3. Check for locale
    const pathnameHasLocale = locales.some(
        locale => pathname.startsWith(`/${locale}/`) || pathname === `/${locale}`
    );

    if (pathnameHasLocale) {
        return NextResponse.next();
    }

    // 4. Redirect to default locale
    // Use clone() to ensure we don't mutate state unexpectedly
    const url = request.nextUrl.clone();

    // Clean redirection logic
    if (pathname === '/') {
        url.pathname = `/${defaultLocale}`;
    } else {
        url.pathname = `/${defaultLocale}${pathname}`;
    }

    return NextResponse.redirect(url);
}

export const config = {
    matcher: [
        /*
         * Match all request paths except for the ones starting with:
         * - _next/static (static files)
         * - _next/image (image optimization files)
         * - favicon.ico, sitemap.xml, robots.txt (metadata files)
         */
        "/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)",
    ],
};
