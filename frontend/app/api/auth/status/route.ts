import { NextRequest, NextResponse } from "next/server";

import { auth0 } from "@/lib/auth0";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const session = await auth0.getSession(request);
  const user = session?.user ?? null;

  return NextResponse.json(
    {
      authenticated: Boolean(user),
      user: user
        ? {
            sub: typeof user.sub === "string" ? user.sub : undefined,
            email: typeof user.email === "string" ? user.email : undefined,
            name:
              typeof user.name === "string"
                ? user.name
                : typeof user.nickname === "string"
                  ? user.nickname
                  : undefined,
            picture: typeof user.picture === "string" ? user.picture : undefined,
          }
        : null,
    },
    {
      headers: {
        "Cache-Control": "no-store, no-cache, must-revalidate",
      },
    },
  );
}
