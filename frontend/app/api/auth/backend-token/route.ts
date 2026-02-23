import { NextRequest, NextResponse } from "next/server";

import { auth0 } from "@/lib/auth0";
import { createBackendInternalToken } from "@/lib/internal-backend-jwt";

export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const session = await auth0.getSession(request);
  const user = session?.user;
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const tokenData = createBackendInternalToken(user);
  if ("error" in tokenData) {
    const status = tokenData.error.startsWith("Invalid user session") ? 401 : 500;
    return NextResponse.json({ error: tokenData.error }, { status });
  }

  return NextResponse.json({
    token: tokenData.token,
    expires_at: tokenData.expiresAtMs,
    user_id: tokenData.userId,
    email: tokenData.email,
  });
}

