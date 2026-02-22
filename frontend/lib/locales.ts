export const DEFAULT_LOCALE = "en" as const;
export const ACTIVE_LOCALES = [DEFAULT_LOCALE] as const;
export const LEGACY_LOCALES = ["es"] as const;

export type AppLocale = (typeof ACTIVE_LOCALES)[number];

const knownLocales = new Set<string>([...ACTIVE_LOCALES, ...LEGACY_LOCALES]);

export function isActiveLocale(locale?: string | null): locale is AppLocale {
  return locale === DEFAULT_LOCALE;
}

export function isLegacyLocale(locale?: string | null): boolean {
  return typeof locale === "string" && LEGACY_LOCALES.includes(locale as never);
}

export function isKnownLocale(locale?: string | null): boolean {
  return typeof locale === "string" && knownLocales.has(locale);
}

export function resolveLocale(locale?: string | null): AppLocale {
  if (isActiveLocale(locale)) return locale;
  return DEFAULT_LOCALE;
}

