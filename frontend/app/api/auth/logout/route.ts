import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const url = request.nextUrl.clone();
  url.pathname = "/auth/logout";
  const returnTo = request.nextUrl.searchParams.get("returnTo");
  if (returnTo && returnTo.startsWith("/") && !returnTo.startsWith("//")) {
    url.searchParams.set("returnTo", returnTo);
  } else {
    url.searchParams.set("returnTo", "/auth/login");
  }
  return NextResponse.redirect(url, 302);
}
