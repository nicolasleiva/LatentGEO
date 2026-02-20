import { Auth0Client } from "@auth0/nextjs-auth0/server";
import type { NextRequest } from "next/server";

// Auth0 v4 client - reads configuration from environment variables automatically:
// - AUTH0_DOMAIN
// - AUTH0_CLIENT_ID
// - AUTH0_CLIENT_SECRET
// - AUTH0_SECRET
// - APP_BASE_URL
const REQUIRED_AUTH0_ENV_VARS = [
  "AUTH0_DOMAIN",
  "AUTH0_CLIENT_ID",
  "AUTH0_CLIENT_SECRET",
  "AUTH0_SECRET",
  "APP_BASE_URL",
] as const;

let auth0Client: Auth0Client | null = null;

const getMissingAuth0EnvVars = () =>
  REQUIRED_AUTH0_ENV_VARS.filter((name) => !process.env[name]?.trim());

const getAuth0Client = () => {
  if (auth0Client) {
    return auth0Client;
  }

  const missing = getMissingAuth0EnvVars();
  if (missing.length > 0) {
    throw new Error(
      `Missing Auth0 environment variables: ${missing.join(", ")}`,
    );
  }

  auth0Client = new Auth0Client();
  return auth0Client;
};

export const auth0 = {
  middleware: (request: NextRequest) => getAuth0Client().middleware(request),
  getSession: (request?: NextRequest) => {
    const getSessionFn = getAuth0Client().getSession as (
      req?: NextRequest,
    ) => ReturnType<Auth0Client["getSession"]>;
    return getSessionFn(request);
  },
};
