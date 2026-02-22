import { describe, expect, it } from "vitest";
import { getExternalIntelligenceBanner } from "@/lib/external-intelligence-status";

describe("external-intelligence-status", () => {
  it("maps unavailable timeout code to timeout message", () => {
    const banner = getExternalIntelligenceBanner({
      status: "unavailable",
      error_code: "AGENT1_LLM_TIMEOUT",
    });

    expect(banner).not.toBeNull();
    expect(banner?.severity).toBe("error");
    expect(banner?.message.toLowerCase()).toContain("timed out");
  });

  it("maps unavailable network code to network message", () => {
    const banner = getExternalIntelligenceBanner({
      status: "unavailable",
      error_code: "AGENT1_LLM_NETWORK",
    });

    expect(banner?.severity).toBe("error");
    expect(banner?.message.toLowerCase()).toContain("network");
  });

  it("maps unavailable core-query-empty code to business-alignment message", () => {
    const banner = getExternalIntelligenceBanner({
      status: "unavailable",
      error_code: "AGENT1_CORE_QUERY_EMPTY",
    });

    expect(banner?.severity).toBe("error");
    expect(banner?.message.toLowerCase()).toContain("business-aligned");
  });

  it("returns generic unavailable message for unknown error codes", () => {
    const banner = getExternalIntelligenceBanner({
      status: "unavailable",
      error_code: "UNKNOWN_CODE",
    });

    expect(banner?.severity).toBe("error");
    expect(banner?.message.toLowerCase()).toContain("currently unavailable");
  });

  it("surfaces warning banner when degraded fallback is used", () => {
    const banner = getExternalIntelligenceBanner({
      status: "ok",
      warning_code: "AGENT1_CORE_FILTER_DEGRADED",
      warning_message: "Applied category-context fallback.",
    });

    expect(banner?.severity).toBe("warning");
    expect(banner?.code).toBe("AGENT1_CORE_FILTER_DEGRADED");
    expect(banner?.message).toBe("Applied category-context fallback.");
  });

  it("returns null when status is ok without warning", () => {
    const banner = getExternalIntelligenceBanner({
      status: "ok",
    });

    expect(banner).toBeNull();
  });
});
