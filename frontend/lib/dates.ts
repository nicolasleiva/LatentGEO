const DEFAULT_STABLE_LOCALE = "en-US";
const DEFAULT_STABLE_TIME_ZONE = "UTC";
const DEFAULT_FALLBACK = "—";

type StableDateFormatOptions = {
  fallback?: string;
  locale?: string | null;
  timeZone?: string;
};

const numberFormatterCache = new Map<string, Intl.NumberFormat>();

const normalizeLocale = (locale?: string | null): string => {
  const trimmed = locale?.trim();
  if (!trimmed) return DEFAULT_STABLE_LOCALE;
  if (/^es(?:[-_]|$)/i.test(trimmed)) return "es-AR";
  if (/^en(?:[-_]|$)/i.test(trimmed)) return DEFAULT_STABLE_LOCALE;
  return trimmed;
};

const parseDate = (value?: string | null): Date | null => {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed;
};

const pad2 = (value: number): string => String(value).padStart(2, "0");

const formatDateParts = (date: Date, locale: string): string => {
  const year = date.getUTCFullYear();
  const month = date.getUTCMonth() + 1;
  const day = date.getUTCDate();

  if (locale === "es-AR") {
    return `${day}/${month}/${year}`;
  }
  return `${month}/${day}/${year}`;
};

export const formatStableDate = (
  value?: string | null,
  options: StableDateFormatOptions = {},
): string => {
  const parsed = parseDate(value);
  if (!parsed) return options.fallback ?? DEFAULT_FALLBACK;

  const locale = normalizeLocale(options.locale);
  const timeZone = options.timeZone ?? DEFAULT_STABLE_TIME_ZONE;
  if (timeZone !== DEFAULT_STABLE_TIME_ZONE) {
    return options.fallback ?? DEFAULT_FALLBACK;
  }

  return formatDateParts(parsed, locale);
};

export const formatStableDateTime = (
  value?: string | null,
  options: StableDateFormatOptions = {},
): string => {
  const parsed = parseDate(value);
  if (!parsed) return options.fallback ?? DEFAULT_FALLBACK;

  const locale = normalizeLocale(options.locale);
  const timeZone = options.timeZone ?? DEFAULT_STABLE_TIME_ZONE;
  if (timeZone !== DEFAULT_STABLE_TIME_ZONE) {
    return options.fallback ?? DEFAULT_FALLBACK;
  }

  const datePart = formatDateParts(parsed, locale);
  const hour24 = parsed.getUTCHours();
  const minute = parsed.getUTCMinutes();

  if (locale === "es-AR") {
    return `${datePart}, ${pad2(hour24)}:${pad2(minute)} UTC`;
  }

  const meridiem = hour24 >= 12 ? "PM" : "AM";
  const hour12 = hour24 % 12 || 12;
  return `${datePart}, ${pad2(hour12)}:${pad2(minute)} ${meridiem} UTC`;
};

export const formatStableNumber = (
  value: number,
  options: {
    fallback?: string;
    locale?: string | null;
    maximumFractionDigits?: number;
    minimumFractionDigits?: number;
  } = {},
): string => {
  if (!Number.isFinite(value)) {
    return options.fallback ?? DEFAULT_FALLBACK;
  }

  const locale = normalizeLocale(options.locale);
  const minimumFractionDigits = options.minimumFractionDigits ?? 0;
  const maximumFractionDigits =
    options.maximumFractionDigits ?? Math.max(minimumFractionDigits, 0);
  const cacheKey = [locale, minimumFractionDigits, maximumFractionDigits].join(
    "|",
  );
  const cached = numberFormatterCache.get(cacheKey);
  if (cached) {
    return cached.format(value);
  }

  const formatter = new Intl.NumberFormat(locale, {
    minimumFractionDigits,
    maximumFractionDigits,
  });
  numberFormatterCache.set(cacheKey, formatter);
  return formatter.format(value);
};
