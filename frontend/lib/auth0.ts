import { Auth0Client } from "@auth0/nextjs-auth0/server";
import type { NextRequest } from "next/server";

// Auth0 v4 client - reads configuration from environment variables automatically:
// - AUTH0_DOMAIN
// - AUTH0_CLIENT_ID
// - AUTH0_CLIENT_SECRET
// - AUTH0_SECRET
// - APP_BASE_URL
const REQUIRED_AUTH0_ENV_VARS: string[] = [
  "AUTH0_DOMAIN",
  "AUTH0_CLIENT_ID",
  "AUTH0_CLIENT_SECRET",
  "AUTH0_SECRET",
  "APP_BASE_URL",
];

let auth0Client: Auth0Client | null = null;
type ServerAccessToken = {
  token: string;
  expiresAt?: number;
  token_type?: string;
  audience?: string;
  scope?: string;
};
type ServerGetAccessTokenOptions = {
  refresh?: boolean;
  audience?: string;
  scope?: string;
  authorizationParameters?: {
    audience?: string;
    scope?: string;
  };
};

const getMissingAuth0EnvVars = () =>
  REQUIRED_AUTH0_ENV_VARS.filter((name) => !process.env[name]?.trim());

const getAuth0Client = () => {
  if (auth0Client) {
    return auth0Client;
  }

  const isTest = process.env.NODE_ENV === "test" || process.env.VITEST === "true";
  const isProduction = process.env.NODE_ENV === "production";
  const missing = getMissingAuth0EnvVars();
  const audience =
    process.env.AUTH0_API_AUDIENCE?.trim() ||
    process.env.NEXT_PUBLIC_AUTH0_API_AUDIENCE?.trim();
  const loginScope =
    process.env.AUTH0_LOGIN_SCOPES?.trim() || "openid profile email";
  const apiScope =
    process.env.AUTH0_API_SCOPES?.trim() ||
    process.env.NEXT_PUBLIC_AUTH0_API_SCOPES?.trim() ||
    "read:app";
  const authorizationScope = Array.from(
    new Set(
      `${loginScope} ${apiScope}`
        .trim()
        .split(/\s+/)
        .filter(Boolean),
    ),
  ).join(" ");

  if (!isTest && isProduction && !audience) {
    missing.push("AUTH0_API_AUDIENCE");
  }

  if (missing.length > 0) {
    throw new Error(
      `Missing Auth0 environment variables: ${missing.join(", ")}`,
    );
  }

  auth0Client = new Auth0Client({
    authorizationParameters: {
      audience,
      scope: authorizationScope,
    },
  });
  return auth0Client;
};

export const auth0 = {
  middleware: (request: NextRequest) => getAuth0Client().middleware(request),
  getSession: (request?: NextRequest) =>
    request
      ? getAuth0Client().getSession(request)
      : getAuth0Client().getSession(),
  getAccessToken: (options?: ServerGetAccessTokenOptions) =>
    getAuth0Client().getAccessToken(options as never) as Promise<ServerAccessToken>,
};
