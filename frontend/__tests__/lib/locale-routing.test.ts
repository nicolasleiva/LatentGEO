import { describe, expect, it, vi } from "vitest";
import {
  getLocalePrefix,
  pushWithLocale,
  replaceWithLocale,
  withLocale,
} from "@/lib/locale-routing";

describe("locale-routing", () => {
  it("uses /en as default and active locale prefix", () => {
    expect(getLocalePrefix("/")).toBe("/en");
    expect(getLocalePrefix("/en/audits")).toBe("/en");
    expect(getLocalePrefix("/es/audits")).toBe("/en");
  });

  it("prefixes unlocalized routes with the active locale", () => {
    expect(withLocale("/en/audits", "/settings")).toBe("/en/settings");
    expect(withLocale("/es/audits", "/settings")).toBe("/en/settings");
    expect(withLocale(undefined, "/audits")).toBe("/en/audits");
    expect(withLocale(undefined, "/")).toBe("/en");
  });

  it("normalizes legacy /es routes to /en", () => {
    expect(withLocale("/en/audits", "/es/pricing")).toBe("/en/pricing");
    expect(withLocale("/es/audits", "/es/docs")).toBe("/en/docs");
    expect(withLocale("/en/audits", "/en/pricing")).toBe("/en/pricing");
  });

  it("keeps absolute URLs, auth routes, and /signin untouched", () => {
    expect(withLocale("/en/audits", "https://example.com")).toBe(
      "https://example.com",
    );
    expect(withLocale("/en/audits", "/auth/login")).toBe("/auth/login");
    expect(withLocale("/en/audits", "/signin")).toBe("/signin");
  });

  it("pushWithLocale and replaceWithLocale delegate normalized URLs", () => {
    const push = vi.fn();
    const replace = vi.fn();

    pushWithLocale({ push }, "/es/audits", "/pricing");
    expect(push).toHaveBeenCalledWith("/en/pricing");

    replaceWithLocale({ push, replace }, "/es/audits", "/es/docs");
    expect(replace).toHaveBeenCalledWith("/en/docs");

    replaceWithLocale({ push }, "/es/audits", "/settings");
    expect(push).toHaveBeenCalledWith("/en/settings");
  });
});
