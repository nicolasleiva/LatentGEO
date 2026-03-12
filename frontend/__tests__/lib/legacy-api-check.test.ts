import { describe, expect, it } from "vitest";

import {
  findLegacyApiMatches,
  hasLegacyApiViolation,
} from "../../lib/legacy-api-check.mjs";

describe("legacy API check", () => {
  const apiPrefix = "/api";
  const buildPath = (suffix: string) => `${apiPrefix}${suffix}`;

  it("allows the internal download proxy endpoint", () => {
    expect(
      hasLegacyApiViolation(`fetch("${buildPath("/audits/42/download-pdf")}")`),
    ).toBe(false);
  });

  it("allows the internal download proxy endpoint with query params", () => {
    expect(
      hasLegacyApiViolation(
        `fetch("${buildPath("/audits/42/download-pdf?foo=1")}")`,
      ),
    ).toBe(false);
  });

  it("still flags legacy endpoints with disallowed suffixes", () => {
    const matches = findLegacyApiMatches(
      `fetch("${buildPath("/audits/42/download-pdf-extra")}")`,
    );

    expect(matches).toHaveLength(1);
    expect(matches[0]?.[0]).toBe(`${apiPrefix}/`);
  });

  it("still flags normal legacy backend paths", () => {
    expect(
      hasLegacyApiViolation(`fetch("${buildPath("/audits/42/overview")}")`),
    ).toBe(true);
  });
});
