import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

type ScenarioResult = {
  card: string;
  tab: string;
  samples_ms: number[];
  p50_ms: number;
  p95_ms: number;
};

const readInt = (raw: string | undefined, fallback: number) => {
  const parsed = Number.parseInt(raw || "", 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
};

const percentile = (values: number[], ratio: number) => {
  const sorted = [...values].sort((a, b) => a - b);
  if (sorted.length === 0) return 0;
  const index = Math.ceil(sorted.length * ratio) - 1;
  return sorted[Math.max(0, Math.min(index, sorted.length - 1))];
};

const reportPath =
  process.env.PERF_REPORT_PATH || "playwright-report/geo-performance.json";
const locale = process.env.PERF_LOCALE || "en";
const auditId = process.env.PERF_AUDIT_ID || "";
const samples = readInt(process.env.PERF_SAMPLES, 20);
const thresholdMs = readInt(process.env.PERF_THRESHOLD_MS, 2000);
const authEmail = process.env.PERF_AUTH_EMAIL || "";
const authPassword = process.env.PERF_AUTH_PASSWORD || "";

const scenarios = [
  {
    cardTestId: "geo-tool-card-commerce",
    tabTestId: "geo-tab-commerce",
    label: "commerce",
  },
  {
    cardTestId: "geo-tool-card-article-engine",
    tabTestId: "geo-tab-article-engine",
    label: "article-engine",
  },
] as const;

const ensureAuthenticated = async (basePath: string, page: Page) => {
  await page.goto(basePath, { waitUntil: "domcontentloaded" });
  const toolCard = page.getByTestId("geo-tool-card-dashboard");
  if (await toolCard.isVisible().catch(() => false)) return;

  if (!authEmail || !authPassword) {
    throw new Error(
      "Auth required for perf:e2e. Set PERF_AUTH_EMAIL and PERF_AUTH_PASSWORD.",
    );
  }

  await page.goto("/api/auth/login", { waitUntil: "domcontentloaded" });
  const emailInput = page
    .locator('input[type="email"], input[name="email"], input[name="username"]')
    .first();
  await emailInput.waitFor({ state: "visible" });
  await emailInput.fill(authEmail);

  const passwordInput = page
    .locator('input[type="password"], input[name="password"]')
    .first();
  await passwordInput.waitFor({ state: "visible" });
  await passwordInput.fill(authPassword);

  const submitButton = page
    .locator(
      'button[type="submit"], button:has-text("Continue"), button:has-text("Log in"), button:has-text("Login")',
    )
    .first();
  await submitButton.click();
  await page.waitForURL(new RegExp(`/audits/${auditId}`), { timeout: 45_000 });
  await expect(page.getByTestId("geo-tool-card-dashboard")).toBeVisible();
};

test("GEO cards p95 stays below threshold", async ({ page }) => {
  test.skip(!auditId, "Set PERF_AUDIT_ID to run GEO performance E2E.");
  const auditPath = `/${locale}/audits/${auditId}`;
  await ensureAuthenticated(auditPath, page);

  const results: ScenarioResult[] = [];

  for (const scenario of scenarios) {
    const durations: number[] = [];
    for (let i = 0; i < samples; i += 1) {
      await page.goto(auditPath, { waitUntil: "domcontentloaded" });
      const card = page.getByTestId(scenario.cardTestId);
      await expect(card).toBeVisible();

      const startedAt = Date.now();
      await Promise.all([
        page.waitForURL(new RegExp(`/audits/${auditId}/geo`), {
          timeout: 20_000,
        }),
        card.click(),
      ]);

      await expect(page.getByTestId("geo-dashboard-page")).toBeVisible();
      await expect(
        page.locator(
          `[data-testid="${scenario.tabTestId}"][data-state="active"]`,
        ),
      ).toBeVisible();

      durations.push(Date.now() - startedAt);
    }

    const p50 = percentile(durations, 0.5);
    const p95 = percentile(durations, 0.95);
    results.push({
      card: scenario.cardTestId,
      tab: scenario.label,
      samples_ms: durations,
      p50_ms: p50,
      p95_ms: p95,
    });
  }

  const report = {
    generated_at: new Date().toISOString(),
    base_url: process.env.PERF_BASE_URL || "",
    audit_id: auditId,
    locale,
    samples_per_scenario: samples,
    threshold_ms: thresholdMs,
    scenarios: results,
  };

  const fullReportPath = path.resolve(reportPath);
  fs.mkdirSync(path.dirname(fullReportPath), { recursive: true });
  fs.writeFileSync(fullReportPath, JSON.stringify(report, null, 2), "utf-8");
  console.log(JSON.stringify(report, null, 2));

  const violations = results.filter((item) => item.p95_ms >= thresholdMs);
  expect(
    violations,
    `GEO performance regression: ${violations
      .map((item) => `${item.tab} p95=${item.p95_ms}ms`)
      .join(", ")}`,
  ).toHaveLength(0);
});
