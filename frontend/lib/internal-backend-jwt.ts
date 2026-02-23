import { createHmac } from "crypto";

const TOKEN_TTL_SECONDS = 5 * 60;

type UserLike = {
  sub?: unknown;
  email?: unknown;
};

const base64UrlEncode = (value: string) =>
  Buffer.from(value)
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");

const encodeJson = (value: Record<string, unknown>) =>
  base64UrlEncode(JSON.stringify(value));

const signJwt = (payload: Record<string, unknown>, secret: string) => {
  const header = { alg: "HS256", typ: "JWT" };
  const encodedHeader = encodeJson(header);
  const encodedPayload = encodeJson(payload);
  const signingInput = `${encodedHeader}.${encodedPayload}`;
  const signature = createHmac("sha256", secret)
    .update(signingInput)
    .digest("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");

  return `${signingInput}.${signature}`;
};

export const getBackendJwtSecret = (): string | null => {
  return process.env.BACKEND_INTERNAL_JWT_SECRET || process.env.SECRET_KEY || null;
};

export const createBackendInternalToken = (user: UserLike) => {
  const userId = typeof user.sub === "string" ? user.sub : "";
  const email =
    typeof user.email === "string" ? user.email.trim().toLowerCase() : null;

  if (!userId) {
    return { error: "Invalid user session: missing sub" } as const;
  }

  const secret = getBackendJwtSecret();
  if (!secret) {
    return {
      error:
        "Server misconfiguration: missing BACKEND_INTERNAL_JWT_SECRET or SECRET_KEY for internal backend token signing",
    } as const;
  }

  const now = Math.floor(Date.now() / 1000);
  const exp = now + TOKEN_TTL_SECONDS;
  const token = signJwt(
    {
      sub: userId,
      email,
      user_email: email,
      iat: now,
      exp,
      iss: "latentgeo-frontend",
    },
    secret,
  );

  return {
    token,
    expiresAtMs: exp * 1000,
    userId,
    email,
  } as const;
};

