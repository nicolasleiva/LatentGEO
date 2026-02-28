import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const url = request.nextUrl.clone();
  const returnTo = request.nextUrl.searchParams.get("returnTo");
  url.pathname = "/auth/login";
  url.search = "";
  if (returnTo && returnTo.startsWith("/") && !returnTo.startsWith("//")) {
    url.searchParams.set("returnTo", returnTo);
  }
  return NextResponse.redirect(url, 302);
}
