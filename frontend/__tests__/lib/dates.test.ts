import {
  formatStableDate,
  formatStableDateTime,
  formatStableNumber,
} from "@/lib/dates";

describe("stable date formatting", () => {
  it("formats dates in UTC so SSR and hydration match", () => {
    expect(formatStableDate("2026-03-10T23:30:00-03:00")).toBe("3/11/2026");
  });

  it("formats timestamps with an explicit timezone", () => {
    expect(formatStableDateTime("2026-03-10T23:30:00-03:00")).toBe(
      "3/11/2026, 02:30 AM UTC",
    );
  });

  it("returns a fallback for invalid values", () => {
    expect(formatStableDate("not-a-date")).toBe("—");
    expect(formatStableDateTime(undefined, { fallback: "N/A" })).toBe("N/A");
  });

  it("keeps locale-specific formatting deterministic without Intl drift", () => {
    expect(formatStableDate("2026-03-10T23:30:00-03:00", { locale: "es" })).toBe(
      "11/3/2026",
    );
    expect(
      formatStableDateTime("2026-03-10T23:30:00-03:00", { locale: "es" }),
    ).toBe("11/3/2026, 02:30 UTC");
  });

  it("formats numbers deterministically across SSR and client", () => {
    expect(formatStableNumber(1234567)).toBe("1,234,567");
    expect(
      formatStableNumber(1234.5, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }),
    ).toBe("1,234.50");
    expect(formatStableNumber(Number.NaN, { fallback: "N/A" })).toBe("N/A");
  });
});
