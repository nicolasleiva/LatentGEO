import { NextRequest } from "next/server";

import { auth0 } from "@/lib/auth0";

const AUTH0_API_AUDIENCE =
  process.env.AUTH0_API_AUDIENCE?.trim() ||
  process.env.NEXT_PUBLIC_AUTH0_API_AUDIENCE?.trim() ||
  "";
const AUTH0_API_SCOPE =
  process.env.AUTH0_API_SCOPES?.trim() ||
  process.env.NEXT_PUBLIC_AUTH0_API_SCOPES?.trim() ||
  "read:app";

export async function getServerProxyAccessToken(
  request: NextRequest,
): Promise<string> {
  const session = await auth0.getSession(request);
  if (!session?.user) {
    throw new Error("unauthorized");
  }

  if (!AUTH0_API_AUDIENCE) {
    throw new Error("missing_audience");
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
    throw new Error("missing_token");
  }

  return tokenResponse.token;
}
