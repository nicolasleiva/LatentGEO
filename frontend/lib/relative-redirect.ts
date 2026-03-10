import { NextResponse } from "next/server";

const normalizePathname = (pathname: string) => {
  if (!pathname.startsWith("/")) {
    return "/";
  }
  if (pathname.startsWith("//")) {
    return "/";
  }
  return pathname;
};

export const relativeRedirect = (
  pathname: string,
  searchParams?: URLSearchParams,
  status = 302,
) => {
  const safePathname = normalizePathname(pathname);
  const query = searchParams?.toString() || "";
  const location = query ? `${safePathname}?${query}` : safePathname;

  return new NextResponse(null, {
    status,
    headers: {
      Location: location,
    },
  });
};
