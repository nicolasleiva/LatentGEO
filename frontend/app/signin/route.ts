import type { NextRequest } from "next/server";
import { relativeRedirect } from "@/lib/relative-redirect";

export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const returnTo = request.nextUrl.searchParams.get("returnTo");
  const searchParams = new URLSearchParams();

  if (returnTo && returnTo.startsWith("/") && !returnTo.startsWith("//")) {
    searchParams.set("returnTo", returnTo);
  }

  return relativeRedirect("/auth/login", searchParams, 302);
}
