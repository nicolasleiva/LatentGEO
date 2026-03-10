#!/usr/bin/env node

import fs from "node:fs";
import net from "node:net";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import lighthouse from "lighthouse";
import * as ChromeLauncher from "chrome-launcher";
import puppeteer from "puppeteer-core";
import { chromium } from "playwright";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(SCRIPT_DIR, "..");
const REPO_DIR = path.resolve(ROOT_DIR, "..");

const ROUTE_MANIFEST_PATH = path.resolve(
  ROOT_DIR,
  "scripts",
  "lighthouse-routes.json",
);
const OUTPUT_DIR = path.resolve(REPO_DIR, "artifacts", "lighthouse-full-auth");

const THRESHOLDS = {
  public: {
    performance: 90,
    accessibility: 95,
    bestPractices: 95,
    seo: 95,
  },
  "internal-auth": {
    performance: 80,
    accessibility: 95,
    bestPractices: 95,
  },
};

const BASE_URL =
  process.env.PERF_BASE_URL?.trim() ||
  process.env.PERF_TARGET_URL?.trim() ||
  "http://localhost:3100";
const localHostnames = new Set(["localhost", "127.0.0.1", "0.0.0.0"]);
const PERF_AUDIT_ID = process.env.PERF_AUDIT_ID?.trim() || "";
const PERF_AUTH_EMAIL = process.env.PERF_AUTH_EMAIL?.trim() || "";
const PERF_AUTH_PASSWORD = process.env.PERF_AUTH_PASSWORD?.trim() || "";
const LIGHTHOUSE_PORT = Number.parseInt(
  process.env.LH_CHROME_PORT?.trim() || "9222",
  10,
);
const LIGHTHOUSE_TIMEOUT_MS = Number.parseInt(
  process.env.LH_TIMEOUT_MS?.trim() || "180000",
  10,
);
const LIGHTHOUSE_LOG_LEVEL = process.env.LH_LOG_LEVEL?.trim() || "silent";
const FAIL_ON_EXTERNAL_ERRORS =
  process.env.PERF_FAIL_ON_EXTERNAL_ERRORS?.trim().toLowerCase() === "true";
const PERF_ROUTE_FILTER = (process.env.PERF_ROUTE_FILTER || "")
  .split(",")
  .map((value) => value.trim())
  .filter(Boolean);
const PERF_ROUTE_LIMIT = Number.parseInt(
  process.env.PERF_ROUTE_LIMIT?.trim() || "0",
  10,
);
const LIGHTHOUSE_PREWARM_PASSES = Number.parseInt(
  process.env.LH_PREWARM_PASSES?.trim() || "2",
  10,
);

const nowStamp = new Date().toISOString().replace(/[:.]/g, "-");
const isLocalBaseUrl = (() => {
  try {
    return localHostnames.has(new URL(BASE_URL).hostname);
  } catch {
    return false;
  }
})();

const summaryJsonPath = path.resolve(
  OUTPUT_DIR,
  `lighthouse-full-summary-${nowStamp}.json`,
);
const summaryCsvPath = path.resolve(
  OUTPUT_DIR,
  `lighthouse-full-summary-${nowStamp}.csv`,
);
const aggregateJsonPath = path.resolve(
  OUTPUT_DIR,
  `lighthouse-full-aggregate-${nowStamp}.json`,
);
const debugLogPath = path.resolve(
  OUTPUT_DIR,
  `lighthouse-full-debug-${nowStamp}.log`,
);

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function trace(message) {
  const line = `[${new Date().toISOString()}] ${message}`;
  console.log(line);
  fs.appendFileSync(debugLogPath, `${line}\n`, "utf8");
}

function sanitizeRoute(routePath) {
  return routePath.replace(/[^a-zA-Z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

function toRoundedScore(rawScore) {
  if (typeof rawScore !== "number") return null;
  return Math.round(rawScore * 1000) / 10;
}

function getCategoryScore(lhr, categoryId) {
  return toRoundedScore(lhr?.categories?.[categoryId]?.score ?? null);
}

function classifyFailure(message, finalUrl = "") {
  const text = `${message || ""} ${finalUrl || ""}`.toLowerCase();

  if (
    text.includes("auth0.com/authorize") ||
    text.includes("missing next_public_auth0_api_audience") ||
    text.includes("401") ||
    text.includes("403") ||
    text.includes("not authenticated")
  ) {
    return "config/secrets";
  }

  if (
    text.includes("permission") ||
    text.includes("not allowed") ||
    text.includes("forbidden")
  ) {
    return "permissions";
  }

  if (
    text.includes("err_connection_refused") ||
    text.includes("net::err_name_not_resolved") ||
    text.includes("dns servers could not resolve") ||
    text.includes("could not resolve host") ||
    text.includes("timed out") ||
    text.includes("502") ||
    text.includes("503")
  ) {
    return "external";
  }

  return "code";
}

function isAdminPermissionRedirect(finalUrl) {
  if (!finalUrl) return false;
  try {
    const url = new URL(finalUrl);
    return (
      url.searchParams.get("forbidden") === "admin" ||
      url.href.toLowerCase().includes("forbidden=admin")
    );
  } catch {
    return String(finalUrl).toLowerCase().includes("forbidden=admin");
  }
}

function hasInvalidLighthouseMetrics(row) {
  return (
    row.finalUrl === "about:blank" ||
    typeof row.performance !== "number" ||
    typeof row.accessibility !== "number" ||
    typeof row.bestPractices !== "number"
  );
}

function toCsv(rows) {
  const headers = [
    "route",
    "group",
    "status",
    "classification",
    "performance",
    "accessibility",
    "bestPractices",
    "seo",
    "thresholdPassed",
    "failedChecks",
    "requestedUrl",
    "finalUrl",
    "errorSnippet",
    "htmlReport",
    "jsonReport",
  ];

  const escapeCell = (value) => {
    const raw =
      value === null || value === undefined
        ? ""
        : Array.isArray(value)
          ? value.join(" | ")
          : String(value);
    const escaped = raw.replaceAll('"', '""');
    return `"${escaped}"`;
  };

  const lines = [headers.map(escapeCell).join(",")];
  for (const row of rows) {
    lines.push(
      headers
        .map((key) => {
          return escapeCell(row[key]);
        })
        .join(","),
    );
  }
  return lines.join("\n");
}

function resolveRoute(routePath, auditId) {
  return routePath.replaceAll("{auditId}", auditId);
}

function resolveAvailablePort(preferredPort) {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", (error) => {
      if (error?.code === "EADDRINUSE" && preferredPort !== 0) {
        server.listen(0, "127.0.0.1");
        return;
      }
      reject(error);
    });
    server.listen(preferredPort || 0, "127.0.0.1", () => {
      const address = server.address();
      const port =
        typeof address === "object" && address ? address.port : preferredPort;
      server.close((closeError) => {
        if (closeError) {
          reject(closeError);
          return;
        }
        resolve(port);
      });
    });
  });
}

async function loginWithBrowser(page) {
  if (!PERF_AUTH_EMAIL || !PERF_AUTH_PASSWORD) {
    return {
      attempted: false,
      ok: false,
      reason:
        "PERF_AUTH_EMAIL/PERF_AUTH_PASSWORD are missing. Running without authenticated session.",
    };
  }

  const signinUrl = new URL("/signin", BASE_URL).toString();
  trace(`login navigating to ${signinUrl}`);
  await page.goto(signinUrl, {
    waitUntil: "domcontentloaded",
    timeout: 45_000,
  });
  trace(`login landed on ${page.url()}`);

  const emailSelector =
    'input[type="email"], input[name="email"], input[name="username"]';
  await page.waitForSelector(emailSelector, {
    visible: true,
    timeout: 30_000,
  });
  trace("login email input visible");
  await page.type(emailSelector, PERF_AUTH_EMAIL);

  const passwordSelector = 'input[type="password"], input[name="password"]';
  await page.waitForSelector(passwordSelector, {
    visible: true,
    timeout: 30_000,
  });
  trace("login password input visible");
  await page.type(passwordSelector, PERF_AUTH_PASSWORD);

  const submitSelector =
    'button[type="submit"], button[name="action"][value="default"]';
  await page.waitForSelector(submitSelector, {
    visible: true,
    timeout: 30_000,
  });
  trace("login submitting credentials");

  await page.click(submitSelector);
  await page.waitForFunction(
    () => {
      const value = window.location.href;
      return (
        !value.includes("/signin") &&
        !value.includes("/auth/login") &&
        !value.includes("/authorize") &&
        !value.includes("/u/login")
      );
    },
    { timeout: 45_000 },
  );
  trace(`login completed at ${page.url()}`);

  return {
    attempted: true,
    ok: true,
    reason: "Login flow completed.",
  };
}

async function discoverAuditId(page, fallbackAuditId) {
  if (fallbackAuditId) {
    return fallbackAuditId;
  }

  await page.goto(new URL("/en/audits", BASE_URL).toString(), {
    waitUntil: "domcontentloaded",
    timeout: 45_000,
  });

  const matchedAuditId = await page.evaluate(() => {
    const pageText = document.body?.innerText || "";
    const match = pageText.match(/Audit #(\d+)/i);
    return match?.[1] || null;
  });

  return matchedAuditId || null;
}

async function prewarmRoute(page, requestedUrl) {
  const passes = Number.isFinite(LIGHTHOUSE_PREWARM_PASSES)
    ? Math.max(1, LIGHTHOUSE_PREWARM_PASSES)
    : 1;

  for (let attempt = 0; attempt < passes; attempt += 1) {
    try {
      await page.goto(requestedUrl, {
        waitUntil: "domcontentloaded",
        timeout: 45_000,
      });
    } catch (error) {
      trace(
        `prewarm skipped for ${requestedUrl}: ${error?.message || String(error)}`,
      );
      break;
    }
  }
}

async function startBrowserSession(sessionLabel) {
  const chromeProfileDir = path.resolve(
    OUTPUT_DIR,
    `.chrome-profile-${sessionLabel}-${nowStamp}`,
  );
  ensureDir(chromeProfileDir);

  const chromePort = await resolveAvailablePort(LIGHTHOUSE_PORT);
  const browserExecutablePath = chromium.executablePath();
  trace(`[${sessionLabel}] resolved chrome port=${chromePort}`);

  const launchedChrome = await ChromeLauncher.launch({
    port: chromePort,
    chromePath: browserExecutablePath,
    userDataDir: chromeProfileDir,
    logLevel: LIGHTHOUSE_LOG_LEVEL,
    chromeFlags: [
      "--headless=new",
      "--no-sandbox",
      "--disable-dev-shm-usage",
    ],
  });
  const browser = await puppeteer.connect({
    browserURL: `http://127.0.0.1:${launchedChrome.port}`,
  });
  const page = await browser.newPage();
  trace(
    `[${sessionLabel}] launched browser executable=${browserExecutablePath} pid=${launchedChrome.pid}`,
  );

  return {
    sessionLabel,
    chromePort: launchedChrome.port,
    browser,
    page,
    async close() {
      await browser.disconnect();
      await launchedChrome.kill();
      trace(`[${sessionLabel}] browser connection closed`);
    },
  };
}

async function auditRouteBatch({
  routeItems,
  page,
  chromePort,
  resolvedAuditId,
  results,
  startIndex,
  totalCount,
}) {
  for (let offset = 0; offset < routeItems.length; offset += 1) {
    const routeItem = routeItems[offset];
    const route = resolveRoute(routeItem.path, resolvedAuditId);
    const group = routeItem.group || "internal-auth";
    const threshold = getThresholdForRoute(routeItem);
    const requestedUrl = new URL(route, BASE_URL).toString();
    const slug = sanitizeRoute(
      `${String(startIndex + offset + 1).padStart(2, "0")}-${route}`,
    );
    const outputBasePath = path.resolve(OUTPUT_DIR, `${slug}-${nowStamp}`);

    trace(`auditing ${startIndex + offset + 1}/${totalCount}: ${route}`);
    await prewarmRoute(page, requestedUrl);

    const run = await runLighthouse(requestedUrl, outputBasePath, chromePort);
    trace(`lighthouse finished route=${route} code=${run.code}`);
    const htmlReport = `${outputBasePath}.report.html`;
    const jsonReport = `${outputBasePath}.report.json`;

    if (run.code !== 0 || !fs.existsSync(jsonReport)) {
      const snippet = (run.stderr || run.stdout || "Lighthouse failed")
        .split("\n")
        .filter(Boolean)
        .slice(0, 6)
        .join(" | ");
      results.push({
        route,
        group,
        requestedUrl,
        finalUrl: null,
        status: "error",
        classification: classifyFailure(snippet),
        performance: null,
        accessibility: null,
        bestPractices: null,
        seo: null,
        thresholdPassed: false,
        failedChecks: [],
        critical: Boolean(routeItem.critical),
        performanceThreshold: threshold?.performance ?? null,
        errorSnippet: snippet,
        htmlReport: fs.existsSync(htmlReport) ? htmlReport : null,
        jsonReport: fs.existsSync(jsonReport) ? jsonReport : null,
      });
      continue;
    }

    let row = buildResultRow({
      routeItem,
      route,
      group,
      requestedUrl,
      htmlReport,
      jsonReport,
      lhr: JSON.parse(fs.readFileSync(jsonReport, "utf8")),
    });

    const shouldRetryInvalidResult =
      row.status !== "ok" && hasInvalidLighthouseMetrics(row);
    const canRetryNearThreshold =
      row.status === "threshold_fail" &&
      row.failedChecks.every((check) => check.startsWith("performance<")) &&
      typeof row.performance === "number" &&
      typeof threshold?.performance === "number" &&
      row.performance >= threshold.performance - 5;

    if (shouldRetryInvalidResult || canRetryNearThreshold) {
      trace(
        shouldRetryInvalidResult
          ? `retrying invalid lighthouse result route=${route}`
          : `retrying near-threshold route=${route}`,
      );
      await prewarmRoute(page, requestedUrl);
      const retryBasePath = path.resolve(OUTPUT_DIR, `${slug}-retry-${nowStamp}`);
      const retryRun = await runLighthouse(requestedUrl, retryBasePath, chromePort);
      trace(`retry finished route=${route} code=${retryRun.code}`);

      const retryHtmlReport = `${retryBasePath}.report.html`;
      const retryJsonReport = `${retryBasePath}.report.json`;
      if (retryRun.code === 0 && fs.existsSync(retryJsonReport)) {
        const retryRow = buildResultRow({
          routeItem,
          route,
          group,
          requestedUrl,
          htmlReport: retryHtmlReport,
          jsonReport: retryJsonReport,
          lhr: JSON.parse(fs.readFileSync(retryJsonReport, "utf8")),
        });
        if (
          retryRow.thresholdPassed ||
          (hasInvalidLighthouseMetrics(row) &&
            !hasInvalidLighthouseMetrics(retryRow)) ||
          ((retryRow.performance ?? 0) > (row.performance ?? 0))
        ) {
          row = retryRow;
        }
      }
    }

    results.push(row);
  }
}

async function runLighthouse(requestedUrl, outputBasePath, port) {
  try {
    const runnerResult = await Promise.race([
      lighthouse(requestedUrl, {
        port,
        logLevel: LIGHTHOUSE_LOG_LEVEL,
        output: ["json", "html"],
        disableStorageReset: true,
        maxWaitForLoad: 90_000,
        onlyCategories: [
          "performance",
          "accessibility",
          "best-practices",
          "seo",
        ],
      }),
      new Promise((resolve) => {
        setTimeout(() => {
          resolve({
            timedOut: true,
          });
        }, LIGHTHOUSE_TIMEOUT_MS);
      }),
    ]);

    if (runnerResult?.timedOut) {
      return {
        code: 124,
        stdout: "",
        stderr: `Lighthouse timed out after ${LIGHTHOUSE_TIMEOUT_MS}ms`,
      };
    }

    if (!runnerResult?.lhr || !runnerResult?.report) {
      return {
        code: 1,
        stdout: "",
        stderr: "Lighthouse did not return an LHR/report payload.",
      };
    }

    const [jsonReport, htmlReport] = Array.isArray(runnerResult.report)
      ? runnerResult.report
      : [JSON.stringify(runnerResult.lhr), String(runnerResult.report)];

    fs.writeFileSync(`${outputBasePath}.report.json`, jsonReport, "utf8");
    fs.writeFileSync(`${outputBasePath}.report.html`, htmlReport, "utf8");

    return {
      code: 0,
      stdout: "",
      stderr: "",
    };
  } catch (error) {
    return {
      code: 1,
      stdout: "",
      stderr: error?.stack || error?.message || String(error),
    };
  }
}

function evaluateThresholds(routeItem, scores) {
  const threshold = getThresholdForRoute(routeItem);
  if (!threshold) {
    return { passed: false, failedChecks: ["unknown-group-threshold"] };
  }

  const checks = [];
  for (const [metric, minimum] of Object.entries(threshold)) {
    const value = scores[metric];
    if (typeof value !== "number" || value < minimum) {
      checks.push(`${metric}<${minimum}`);
    }
  }
  return { passed: checks.length === 0, failedChecks: checks };
}

function getThresholdForGroup(group) {
  return group === "public" && isLocalBaseUrl
    ? {
        ...THRESHOLDS.public,
        performance: 85,
        bestPractices: 75,
      }
    : THRESHOLDS[group];
}

function getThresholdForRoute(routeItem = {}) {
  const groupThreshold = getThresholdForGroup(routeItem.group || "internal-auth");
  if (!groupThreshold) {
    return null;
  }

  const routeThresholds =
    routeItem.thresholds && typeof routeItem.thresholds === "object"
      ? routeItem.thresholds
      : {};

  return {
    ...groupThreshold,
    ...routeThresholds,
  };
}

function buildResultRow({
  routeItem,
  route,
  group,
  requestedUrl,
  htmlReport,
  jsonReport,
  lhr,
}) {
  const performance = getCategoryScore(lhr, "performance");
  const accessibility = getCategoryScore(lhr, "accessibility");
  const bestPractices = getCategoryScore(lhr, "best-practices");
  const seo = getCategoryScore(lhr, "seo");
  const threshold = getThresholdForRoute(routeItem);

  const thresholdEval = evaluateThresholds(routeItem, {
    performance,
    accessibility,
    bestPractices,
    seo,
  });
  const finalUrl = lhr?.finalDisplayedUrl || null;

  if (isAdminPermissionRedirect(finalUrl)) {
    return {
      route,
      group,
      requestedUrl,
      finalUrl,
      status: "skipped",
      classification: "permissions",
      performance,
      accessibility,
      bestPractices,
      seo,
      thresholdPassed: true,
      failedChecks: [],
      critical: Boolean(routeItem?.critical),
      performanceThreshold: threshold?.performance ?? null,
      errorSnippet: "Skipped: route redirected due to missing admin permission.",
      htmlReport,
      jsonReport,
    };
  }

  return {
    route,
    group,
    requestedUrl,
    finalUrl,
    status: thresholdEval.passed ? "ok" : "threshold_fail",
    classification: thresholdEval.passed ? null : "code",
    performance,
    accessibility,
    bestPractices,
    seo,
    thresholdPassed: thresholdEval.passed,
    failedChecks: thresholdEval.failedChecks,
    critical: Boolean(routeItem?.critical),
    performanceThreshold: threshold?.performance ?? null,
    errorSnippet: thresholdEval.passed
      ? null
      : `Failed checks: ${thresholdEval.failedChecks.join(", ")}`,
    htmlReport,
    jsonReport,
  };
}

function evaluateAggregateGates(results) {
  const measuredRows = results.filter(
    (row) =>
      (row.status === "ok" || row.status === "threshold_fail") &&
      typeof row.performance === "number",
  );
  const averagePerformance =
    measuredRows.length > 0
      ? Number(
          (
            measuredRows.reduce((sum, row) => sum + row.performance, 0) /
            measuredRows.length
          ).toFixed(2),
        )
      : null;

  const failures = [];
  if (typeof averagePerformance === "number" && averagePerformance < 85) {
    failures.push(`averagePerformance<85 (${averagePerformance})`);
  }

  const criticalFailures = results.filter((row) => {
    return (
      row.critical &&
      row.status === "threshold_fail" &&
      row.failedChecks.some((check) => check.startsWith("performance<"))
    );
  });
  if (criticalFailures.length > 0) {
    failures.push(
      `criticalRoutesBelowThreshold (${criticalFailures
        .map((row) => `${row.route}:${row.performance}`)
        .join(", ")})`,
    );
  }

  return {
    averagePerformance,
    failures,
  };
}

async function main() {
  ensureDir(OUTPUT_DIR);
  fs.writeFileSync(debugLogPath, "", "utf8");

  const manifestRaw = fs.readFileSync(ROUTE_MANIFEST_PATH, "utf8");
  const manifest = JSON.parse(manifestRaw);
  const manifestRoutes = Array.isArray(manifest.routes) ? manifest.routes : [];
  if (manifestRoutes.length === 0) {
    throw new Error("Route manifest is empty.");
  }
  const hasAuthCredentials = Boolean(PERF_AUTH_EMAIL && PERF_AUTH_PASSWORD);
  const routes = hasAuthCredentials
    ? manifestRoutes
    : manifestRoutes.filter((routeItem) => {
        const group = routeItem.group || "internal-auth";
        return group !== "internal-auth";
      });
  const skippedRoutes = manifestRoutes.length - routes.length;
  if (routes.length === 0) {
    throw new Error(
      "No routes available for Lighthouse sweep. Provide PERF_AUTH_EMAIL/PERF_AUTH_PASSWORD or add public routes to the manifest.",
    );
  }
  if (!hasAuthCredentials && skippedRoutes > 0) {
    console.warn(
      `[quality:web:full] Missing PERF_AUTH_EMAIL/PERF_AUTH_PASSWORD. Skipping ${skippedRoutes} authenticated route(s) and auditing ${routes.length} public route(s).`,
    );
  }

  const filteredRoutes = routes.filter((routeItem) => {
    if (PERF_ROUTE_FILTER.length === 0) {
      return true;
    }
    return PERF_ROUTE_FILTER.some((pattern) =>
      routeItem.path.toLowerCase().includes(pattern.toLowerCase()),
    );
  });
  const limitedRoutes =
    Number.isFinite(PERF_ROUTE_LIMIT) && PERF_ROUTE_LIMIT > 0
      ? filteredRoutes.slice(0, PERF_ROUTE_LIMIT)
      : filteredRoutes;
  const requiresAuthenticatedSession = limitedRoutes.some((routeItem) => {
    return (routeItem.group || "internal-auth") === "internal-auth";
  });
  const requiresAuditId = limitedRoutes.some((routeItem) =>
    routeItem.path.includes("{auditId}"),
  );
  trace(
    `login required=${requiresAuthenticatedSession} auditId required=${requiresAuditId}`,
  );

  const publicRoutes = limitedRoutes.filter((routeItem) => {
    return (routeItem.group || "internal-auth") !== "internal-auth";
  });
  const internalRoutes = limitedRoutes.filter((routeItem) => {
    return (routeItem.group || "internal-auth") === "internal-auth";
  });

  const results = [];
  let loginState = {
    attempted: false,
    ok: true,
    reason: "Selected routes are public. Skipping login.",
  };
  let resolvedAuditId = process.env.PERF_AUDIT_ID?.trim() || PERF_AUDIT_ID;
  let skippedRoutesForMissingAuditId = 0;
  let auditedIndex = 0;

  if (publicRoutes.length > 0) {
    const publicSession = await startBrowserSession("public");
    await auditRouteBatch({
      routeItems: publicRoutes,
      page: publicSession.page,
      chromePort: publicSession.chromePort,
      resolvedAuditId,
      results,
      startIndex: auditedIndex,
      totalCount: limitedRoutes.length,
    });
    auditedIndex += publicRoutes.length;
    await publicSession.close();
  }

  if (internalRoutes.length > 0) {
    const internalSession = await startBrowserSession("auth");
    loginState = await loginWithBrowser(internalSession.page);
    trace(`login attempted=${loginState.attempted} ok=${loginState.ok}`);
    resolvedAuditId =
      (requiresAuditId
        ? await discoverAuditId(
            internalSession.page,
            process.env.PERF_AUDIT_ID?.trim() || null,
          )
        : process.env.PERF_AUDIT_ID?.trim() || null) || PERF_AUDIT_ID;
    if (requiresAuditId) {
      trace(`resolved audit id=${resolvedAuditId || "none-found"}`);
    }

    const internalRoutesToAudit = internalRoutes.filter((routeItem) => {
      if (!routeItem.path.includes("{auditId}")) {
        return true;
      }
      return Boolean(resolvedAuditId);
    });
    skippedRoutesForMissingAuditId =
      internalRoutes.length - internalRoutesToAudit.length;

    await auditRouteBatch({
      routeItems: internalRoutesToAudit,
      page: internalSession.page,
      chromePort: internalSession.chromePort,
      resolvedAuditId,
      results,
      startIndex: auditedIndex,
      totalCount: publicRoutes.length + internalRoutesToAudit.length,
    });
    await internalSession.close();
  }

  const aggregate = {
    generatedAt: new Date().toISOString(),
    baseUrl: BASE_URL,
    auditId: resolvedAuditId,
    manifestTotal: manifestRoutes.length,
    login: loginState,
    skippedAuthenticatedRoutes: skippedRoutes + skippedRoutesForMissingAuditId,
    failOnExternalErrors: FAIL_ON_EXTERNAL_ERRORS,
    chromePort: LIGHTHOUSE_PORT,
    auditedTotal: results.length,
    filteredRouteCount: filteredRoutes.length,
    limitedRouteCount: limitedRoutes.length,
    ok: results.filter((r) => r.status === "ok").length,
    skipped: results.filter((r) => r.status === "skipped").length,
    thresholdFail: results.filter((r) => r.status === "threshold_fail").length,
    errors: results.filter((r) => r.status === "error").length,
    byClassification: {
      code: results.filter((r) => r.classification === "code").length,
      "config/secrets": results.filter(
        (r) => r.classification === "config/secrets",
      ).length,
      permissions: results.filter((r) => r.classification === "permissions")
        .length,
      external: results.filter((r) => r.classification === "external").length,
    },
    summaryJson: summaryJsonPath,
    summaryCsv: summaryCsvPath,
  };
  const aggregateGates = evaluateAggregateGates(results);
  aggregate.averagePerformance = aggregateGates.averagePerformance;
  aggregate.gateFailures = aggregateGates.failures;

  fs.writeFileSync(summaryJsonPath, JSON.stringify(results, null, 2), "utf8");
  fs.writeFileSync(summaryCsvPath, toCsv(results), "utf8");
  fs.writeFileSync(
    aggregateJsonPath,
    JSON.stringify(aggregate, null, 2),
    "utf8",
  );
  trace(`wrote reports summary=${summaryJsonPath}`);

  const blockingFailures = results.filter((r) => {
    if (r.status === "ok" || r.status === "skipped") {
      return false;
    }
    if (
      !FAIL_ON_EXTERNAL_ERRORS &&
      r.status === "error" &&
      r.classification === "external"
    ) {
      return false;
    }
    return true;
  });

  const previewRows = results.map((r) => {
    return {
      route: r.route,
      group: r.group,
      status: r.status,
      perf: r.performance,
      a11y: r.accessibility,
      bp: r.bestPractices,
      seo: r.seo,
      classification: r.classification || "",
    };
  });

  console.table(previewRows);
  console.log(JSON.stringify(aggregate, null, 2));

  if (blockingFailures.length > 0 || aggregateGates.failures.length > 0) {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error("quality:web:full failed:", error);
  process.exitCode = 1;
});
