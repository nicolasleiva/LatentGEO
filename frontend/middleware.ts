import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

export async function middleware(request: NextRequest) {
    const { pathname } = request.nextUrl;

    // Skip middleware for static files and API routes
    if (
        pathname.startsWith('/_next') ||
        pathname.startsWith('/api') ||
        pathname.includes('.') // static files
    ) {
        return NextResponse.next();
    }

    // Try to use Auth0 middleware, but don't fail if it's not configured
    try {
        const { auth0 } = await import('./lib/auth0');
        return await auth0.middleware(request);
    } catch (error) {
        // Auth0 not configured or error - continue without auth
        console.warn('Auth0 middleware skipped:', error instanceof Error ? error.message : 'Unknown error');
        return NextResponse.next();
    }
}

export const config = {
    matcher: [
        "/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)",
    ],
};
