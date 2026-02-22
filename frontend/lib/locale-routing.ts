import {
  DEFAULT_LOCALE,
  isActiveLocale,
  isKnownLocale,
  isLegacyLocale,
} from "@/lib/locales";

function isAbsoluteUrl(href: string): boolean {
  return /^https?:\/\//i.test(href);
}

function normalizePath(href: string): string {
  if (!href) return "/";
  if (href.startsWith("/")) return href;
  return `/${href}`;
}

export function getLocalePrefix(pathname?: string | null): `/${string}` {
  const firstSegment = pathname?.split("/").filter(Boolean)[0];
  if (isActiveLocale(firstSegment)) {
    return `/${firstSegment}`;
  }
  return `/${DEFAULT_LOCALE}`;
}

export function withLocale(pathname: string | null | undefined, href: string): string {
  if (isAbsoluteUrl(href)) return href;
  if (href.startsWith("/auth/")) return href;

  const normalized = normalizePath(href);
  if (normalized === "/") return getLocalePrefix(pathname);

  const firstSegment = normalized.split("/").filter(Boolean)[0];
  if (isActiveLocale(firstSegment)) return normalized;
  if (isLegacyLocale(firstSegment)) {
    const rest = normalized.slice(`/${firstSegment}`.length) || "";
    return `/${DEFAULT_LOCALE}${rest}`;
  }
  if (isKnownLocale(firstSegment)) return normalized;

  return `${getLocalePrefix(pathname)}${normalized}`;
}

type PushLikeRouter = {
  push: (href: string) => void;
  replace?: (href: string) => void;
};

export function pushWithLocale(
  router: PushLikeRouter,
  pathname: string | null | undefined,
  href: string,
): void {
  router.push(withLocale(pathname, href));
}

export function replaceWithLocale(
  router: PushLikeRouter,
  pathname: string | null | undefined,
  href: string,
): void {
  if (typeof router.replace !== "function") {
    router.push(withLocale(pathname, href));
    return;
  }
  router.replace(withLocale(pathname, href));
}
