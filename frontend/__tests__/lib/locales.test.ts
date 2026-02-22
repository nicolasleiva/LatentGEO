import { describe, expect, it } from "vitest";
import {
  DEFAULT_LOCALE,
  isActiveLocale,
  isKnownLocale,
  isLegacyLocale,
  resolveLocale,
} from "@/lib/locales";

describe("locales", () => {
  it("defines en as default and active locale", () => {
    expect(DEFAULT_LOCALE).toBe("en");
    expect(isActiveLocale("en")).toBe(true);
    expect(isActiveLocale("es")).toBe(false);
  });

  it("tracks known and legacy locales", () => {
    expect(isKnownLocale("en")).toBe(true);
    expect(isKnownLocale("es")).toBe(true);
    expect(isKnownLocale("fr")).toBe(false);
    expect(isLegacyLocale("es")).toBe(true);
    expect(isLegacyLocale("en")).toBe(false);
  });

  it("always resolves unknown or legacy locale to /en", () => {
    expect(resolveLocale("en")).toBe("en");
    expect(resolveLocale("es")).toBe("en");
    expect(resolveLocale("fr")).toBe("en");
    expect(resolveLocale(undefined)).toBe("en");
  });
});
