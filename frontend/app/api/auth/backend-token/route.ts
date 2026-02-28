import { NextRequest, NextResponse } from "next/server";

import { auth0 } from "@/lib/auth0";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    const audience =
      process.env.AUTH0_API_AUDIENCE?.trim() ||
      process.env.NEXT_PUBLIC_AUTH0_API_AUDIENCE?.trim() ||
      "";
    const scope =
      process.env.AUTH0_API_SCOPES?.trim() ||
      process.env.NEXT_PUBLIC_AUTH0_API_SCOPES?.trim() ||
      "read:app";

    if (!audience) {
      return NextResponse.json(
        { error: "Server misconfigured: AUTH0_API_AUDIENCE is missing" },
        { status: 500 },
      );
    }

    const tokenResponse = await auth0.getAccessToken({
      refresh: false,
      audience,
      scope,
      authorizationParameters: {
        audience,
        scope,
      },
    });

    if (!tokenResponse?.token) {
      return NextResponse.json(
        { error: "Unauthorized: missing Auth0 access token" },
        { status: 401 },
      );
    }

    return NextResponse.json({
      token: tokenResponse.token,
      expires_at: tokenResponse.expiresAt
        ? tokenResponse.expiresAt * 1000
        : undefined,
      token_type: tokenResponse.token_type,
      audience: tokenResponse.audience,
      scope: tokenResponse.scope,
    });
  } catch {
    return NextResponse.json(
      { error: "Unauthorized: missing Auth0 session" },
      { status: 401 },
    );
  }
}
