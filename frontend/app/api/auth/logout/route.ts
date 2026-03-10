import type { NextRequest } from "next/server";
import { relativeRedirect } from "@/lib/relative-redirect";

export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const searchParams = new URLSearchParams();
  const returnTo = request.nextUrl.searchParams.get("returnTo");
  if (returnTo && returnTo.startsWith("/") && !returnTo.startsWith("//")) {
    searchParams.set("returnTo", returnTo);
  } else {
    searchParams.set("returnTo", "/auth/login");
  }
  return relativeRedirect("/auth/logout", searchParams, 302);
}
