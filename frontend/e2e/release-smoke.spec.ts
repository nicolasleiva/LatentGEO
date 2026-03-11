import { expect, test, type BrowserContext, type Page } from "@playwright/test";

const baseUrl = process.env.RELEASE_BASE_URL || process.env.PERF_BASE_URL || "http://localhost:3000";
const apiUrl = process.env.RELEASE_API_URL || process.env.PERF_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const locale = process.env.RELEASE_LOCALE || process.env.PERF_LOCALE || "en";
const seededAuditId = process.env.RELEASE_AUDIT_ID || process.env.PERF_AUDIT_ID || "28";
const authEmail = process.env.RELEASE_AUTH_EMAIL || process.env.PERF_AUTH_EMAIL || "";
const authPassword = process.env.RELEASE_AUTH_PASSWORD || process.env.PERF_AUTH_PASSWORD || "";

const isRedirectAbort = (error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  return message.includes("net::ERR_ABORTED");
};

const isAuthUrl = (value: string) =>
  value.includes("/signin") ||
  value.includes("/auth/login") ||
  value.includes("/authorize") ||
  value.includes("/u/login");

const navigateWithAuthRedirectTolerance = async (page: Page, target: string) => {
  try {
    await page.goto(target, { waitUntil: "domcontentloaded" });
  } catch (error) {
    if (!isRedirectAbort(error)) {
      throw error;
    }
  }
};

const ensureAuthenticated = async (page: Page, targetPath: string) => {
  const targetUrl = new URL(targetPath, baseUrl).toString();
  await navigateWithAuthRedirectTolerance(page, targetUrl);

  if (!isAuthUrl(page.url())) {
    return;
  }

  if (!authEmail || !authPassword) {
    throw new Error(
      "Auth required for release smoke. Set RELEASE_AUTH_EMAIL/RELEASE_AUTH_PASSWORD or PERF_AUTH_EMAIL/PERF_AUTH_PASSWORD.",
    );
  }

  await navigateWithAuthRedirectTolerance(
    page,
    new URL("/signin", baseUrl).toString(),
  );

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
  await page.waitForURL((url) => !isAuthUrl(url.toString()), {
    timeout: 45_000,
  });
  await navigateWithAuthRedirectTolerance(page, targetUrl);
};

const waitForVisibleText = async (page: Page, value: string | RegExp) => {
  const locator = page.getByText(value).first();
  await expect(locator).toBeVisible();
};

const waitForAnyVisibleText = async (
  page: Page,
  values: Array<string | RegExp>,
  timeoutMs = 45_000,
) => {
  const deadline = Date.now() + timeoutMs;
  let lastError: Error | null = null;

  while (Date.now() < deadline) {
    for (const value of values) {
      try {
        await expect(page.getByText(value).first()).toBeVisible({ timeout: 1_500 });
        return;
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));
      }
    }
    await page.waitForTimeout(500);
  }

  throw lastError ?? new Error("Expected at least one matching artifact state to be visible.");
};

const waitForAnyVisibleButton = async (
  page: Page,
  names: RegExp[],
  timeoutMs = 45_000,
) => {
  const deadline = Date.now() + timeoutMs;
  let lastError: Error | null = null;

  while (Date.now() < deadline) {
    for (const name of names) {
      try {
        await expect(page.getByRole("button", { name }).first()).toBeVisible({
          timeout: 1_500,
        });
        return;
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));
      }
    }
    await page.waitForTimeout(500);
  }

  throw lastError ?? new Error("Expected at least one matching button state to be visible.");
};

const openAuthenticatedRoute = async (page: Page, routePath: string) => {
  const routeUrl = new URL(routePath, baseUrl).toString();
  await navigateWithAuthRedirectTolerance(page, routeUrl);
  if (isAuthUrl(page.url())) {
    await ensureAuthenticated(page, routePath);
  }
};

const auditId = seededAuditId;
const baseAuditPath = `/${locale}/audits/${auditId}`;
let sharedContext: BrowserContext | null = null;

const trackCriticalFailures = (page: Page) => {
  const criticalFailures: string[] = [];
  const seenFailures = new Set<string>();
  const baseOrigin = new URL(baseUrl).origin;
  const apiOrigin = new URL(apiUrl).origin;

  const rememberFailure = (message: string) => {
    if (seenFailures.has(message)) return;
    seenFailures.add(message);
    criticalFailures.push(message);
  };

  page.on("pageerror", (error) => {
    rememberFailure(`pageerror: ${error.message}`);
  });

  page.on("response", (response) => {
    const url = response.url();
    const isAppOrApiRequest =
      url.startsWith(baseOrigin) ||
      url.startsWith(apiOrigin) ||
      url.includes("/api/v1/");
    if (!isAppOrApiRequest) return;
    if (response.status() >= 500) {
      rememberFailure(`http ${response.status()} ${url}`);
    }
  });

  return criticalFailures;
};

const assertNoCriticalFailures = (criticalFailures: string[]) => {
  expect(criticalFailures).toEqual([]);
};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ browser }) => {
  sharedContext = await browser.newContext({ acceptDownloads: true });
  const page = await sharedContext.newPage();
  try {
    await ensureAuthenticated(page, baseAuditPath);
  } finally {
    await page.close();
  }
});

test.afterAll(async () => {
  await sharedContext?.close();
  sharedContext = null;
});

const withSharedPage = async (run: (page: Page) => Promise<void>) => {
  if (!sharedContext) {
    throw new Error("Release smoke context was not initialized.");
  }

  const page = await sharedContext.newPage();
  try {
    await run(page);
  } finally {
    await page.close();
  }
};

test("audit detail renders without 500s", async () => {
  test.setTimeout(180_000);
  await withSharedPage(async (page) => {
    const criticalFailures = trackCriticalFailures(page);
    await openAuthenticatedRoute(page, baseAuditPath);
    await expect(page.getByTestId("geo-tool-card-dashboard")).toBeVisible();
    await expect(page.getByTestId("geo-tool-card-commerce")).toBeVisible();
    await expect(page.getByTestId("geo-tool-card-article-engine")).toBeVisible();
    await waitForVisibleText(page, /Execution Tool Suite/i);
    await expect(page.getByRole("button", { name: /Export PDF/i })).toBeVisible();

    await page.getByRole("tab", { name: "Narrative" }).click();
    await waitForVisibleText(page, /Narrative Report \(Markdown\)/i);

    await page.getByRole("tab", { name: "Execution Plan" }).click();
    await waitForVisibleText(page, /Execution Plan/i);
    assertNoCriticalFailures(criticalFailures);
  });
});

test("analytics and GEO pages render without 500s", async () => {
  test.setTimeout(180_000);
  await withSharedPage(async (page) => {
    const criticalFailures = trackCriticalFailures(page);

    await openAuthenticatedRoute(page, `/${locale}/analytics/${auditId}`);
    await waitForVisibleText(page, /Analytics:/i);
    await waitForVisibleText(page, /Competitor Benchmark/i);

    await openAuthenticatedRoute(page, `${baseAuditPath}/geo`);
    await expect(page.getByTestId("geo-dashboard-page")).toBeVisible();
    await waitForVisibleText(page, /GEO Command Center/i);
    await waitForVisibleText(page, /Priority Query Opportunities/i);

    await openAuthenticatedRoute(page, `${baseAuditPath}/geo?tab=commerce`);
    await expect(page.getByTestId("geo-tab-commerce")).toBeVisible();
    await waitForVisibleText(page, /Commerce Query Analyzer/i);

    await openAuthenticatedRoute(page, `${baseAuditPath}/geo?tab=article-engine`);
    await expect(page.getByTestId("geo-tab-article-engine")).toBeVisible();
    await waitForVisibleText(page, /Generate Article Batch/i);
    assertNoCriticalFailures(criticalFailures);
  });
});

test("search datasets render without 500s", async () => {
  test.setTimeout(180_000);
  await withSharedPage(async (page) => {
    const criticalFailures = trackCriticalFailures(page);

    const routeChecks = [
      {
        path: `${baseAuditPath}/keywords`,
        heading: /Semantic Keyword Research/i,
        detail: /Keyword Opportunities/i,
      },
      {
        path: `${baseAuditPath}/backlinks`,
        heading: /Link & Mention Analysis/i,
        detail: /Start Analysis/i,
      },
      {
        path: `${baseAuditPath}/rank-tracking`,
        heading: /Rank Tracking/i,
        detail: /Ranking History/i,
      },
      {
        path: `${baseAuditPath}/llm-visibility`,
        heading: /LLM Visibility Tracker/i,
        detail: /Brand Name/i,
      },
      {
        path: `${baseAuditPath}/ai-content`,
        heading: /AI Content Strategy/i,
        detail: /Generate Suggestions/i,
      },
    ];

    for (const route of routeChecks) {
      await openAuthenticatedRoute(page, route.path);
      await waitForVisibleText(page, route.heading);
      await waitForVisibleText(page, route.detail);
    }
    assertNoCriticalFailures(criticalFailures);
  });
});

test("delivery integrations render without 500s", async () => {
  test.setTimeout(240_000);
  await withSharedPage(async (page) => {
    const criticalFailures = trackCriticalFailures(page);

    await openAuthenticatedRoute(page, `${baseAuditPath}/github-auto-fix`);
    await waitForVisibleText(page, /GitHub Delivery Agent/i);
    await expect(
      page
        .getByRole("button", { name: /Connect GitHub Workspace/i })
        .or(page.getByText(/GitHub Connected/i)),
    ).toBeVisible();

    await openAuthenticatedRoute(page, `${baseAuditPath}/odoo-delivery`);
    await waitForVisibleText(page, /Odoo Delivery Pack/i);
    await expect(
      page
        .getByText(/Connect a real Odoo instance/i)
        .or(page.getByText(/Guided Odoo Briefing/i)),
    ).toBeVisible();

    await openAuthenticatedRoute(page, `/${locale}/integrations/hubspot/connect`);
    await waitForVisibleText(page, /Connect HubSpot/i);
    assertNoCriticalFailures(criticalFailures);
  });
});

test("reports render and an existing PDF downloads without 500s", async () => {
  test.setTimeout(180_000);
  await withSharedPage(async (page) => {
    const criticalFailures = trackCriticalFailures(page);

    await openAuthenticatedRoute(page, `/${locale}/reports`);
    await waitForVisibleText(page, /^Reports$/i);

    const auditIdInput = page
      .locator('input[placeholder*="123"], input[inputmode="numeric"]')
      .first();
    await auditIdInput.fill(auditId);
    await page.getByRole("button", { name: /^Load$/i }).click();

    await expect(page.getByText(/Unable to load reports\./i)).toHaveCount(0);
    await waitForVisibleText(page, /Report #/i);

    const downloadButton = page
      .getByRole("button", { name: /^Download$/i })
      .first();
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      downloadButton.click(),
    ]);
    expect(await download.suggestedFilename()).toMatch(/report-\d+\.pdf/i);
    assertNoCriticalFailures(criticalFailures);
  });
});

test("artifact state survives navigation and reload", async () => {
  test.setTimeout(300_000);
  await withSharedPage(async (page) => {
    const criticalFailures = trackCriticalFailures(page);

    await openAuthenticatedRoute(page, baseAuditPath);
    await waitForVisibleText(page, /Execution Tool Suite/i);

    const pageSpeedButton = page.getByRole("button", {
      name: /PageSpeed/i,
    });
    await expect(pageSpeedButton).toBeVisible();
    await pageSpeedButton.click();

    await waitForAnyVisibleButton(page, [
      /Queued PageSpeed/i,
      /Running PageSpeed/i,
      /Refresh PageSpeed/i,
    ]);

    const pdfButton = page.getByRole("button", {
      name: /Export PDF|Queued for PDF|Waiting on PageSpeed|Building PDF|Download PDF|Retry PDF/i,
    });
    await expect(pdfButton).toBeVisible();
    await pdfButton.click();

    await waitForAnyVisibleText(page, [
      /PDF generation queued/i,
      /waiting for the active PageSpeed pipeline/i,
      /PDF generation in progress/i,
      /PDF ready/i,
      /PageSpeed queued/i,
      /PageSpeed analysis in progress/i,
      /PageSpeed ready/i,
    ]);

    await openAuthenticatedRoute(page, `${baseAuditPath}/keywords`);
    await waitForVisibleText(page, /Semantic Keyword Research/i);

    await openAuthenticatedRoute(page, baseAuditPath);
    await waitForAnyVisibleText(page, [
      /waiting for the active PageSpeed pipeline/i,
      /PDF generation in progress/i,
      /PDF ready/i,
      /PageSpeed queued/i,
      /PageSpeed analysis in progress/i,
      /PageSpeed ready/i,
    ]);

    await page.reload({ waitUntil: "domcontentloaded" });
    await waitForVisibleText(page, /Execution Tool Suite/i);
    await waitForAnyVisibleButton(page, [
      /Queued PageSpeed/i,
      /Running PageSpeed/i,
      /Refresh PageSpeed/i,
      /Queued for PDF/i,
      /Waiting on PageSpeed/i,
      /Building PDF/i,
      /Download PDF/i,
      /Retry PDF/i,
      /Export PDF/i,
    ]);

    assertNoCriticalFailures(criticalFailures);
  });
});
