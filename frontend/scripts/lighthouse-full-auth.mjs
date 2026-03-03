#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
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
    performance: 85,
    accessibility: 95,
    bestPractices: 95,
  },
};

const BASE_URL =
  process.env.PERF_BASE_URL?.trim() ||
  process.env.PERF_TARGET_URL?.trim() ||
  "http://127.0.0.1:3100";
const PERF_AUDIT_ID = process.env.PERF_AUDIT_ID?.trim() || "1";
const PERF_AUTH_EMAIL = process.env.PERF_AUTH_EMAIL?.trim() || "";
const PERF_AUTH_PASSWORD = process.env.PERF_AUTH_PASSWORD?.trim() || "";
const LIGHTHOUSE_PORT = Number.parseInt(
  process.env.LH_CHROME_PORT?.trim() || "9222",
  10,
);

const nowStamp = new Date().toISOString().replace(/[:.]/g, "-");

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

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
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
    text.includes("timed out") ||
    text.includes("502") ||
    text.includes("503")
  ) {
    return "external";
  }

  return "code";
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

function resolveRoute(routePath) {
  return routePath.replaceAll("{auditId}", PERF_AUDIT_ID);
}

async function loginWithPlaywright(page) {
  if (!PERF_AUTH_EMAIL || !PERF_AUTH_PASSWORD) {
    return {
      attempted: false,
      ok: false,
      reason:
        "PERF_AUTH_EMAIL/PERF_AUTH_PASSWORD are missing. Running without authenticated session.",
    };
  }

  const signinUrl = new URL("/signin", BASE_URL).toString();
  await page.goto(signinUrl, { waitUntil: "domcontentloaded" });

  const emailInput = page
    .locator('input[type="email"], input[name="email"], input[name="username"]')
    .first();
  await emailInput.waitFor({ state: "visible", timeout: 30_000 });
  await emailInput.fill(PERF_AUTH_EMAIL);

  const passwordInput = page
    .locator('input[type="password"], input[name="password"]')
    .first();
  await passwordInput.waitFor({ state: "visible", timeout: 30_000 });
  await passwordInput.fill(PERF_AUTH_PASSWORD);

  const submit = page
    .locator(
      'button[type="submit"], button:has-text("Continue"), button:has-text("Log in"), button:has-text("Login")',
    )
    .first();

  await Promise.all([
    submit.click(),
    page
      .waitForURL(
        (url) => {
          const value = url.toString();
          return !value.includes("/signin") && !value.includes("/auth/login");
        },
        { timeout: 45_000 },
      )
      .catch(() => null),
  ]);

  return {
    attempted: true,
    ok: true,
    reason: "Login flow completed.",
  };
}

function runLighthouse(requestedUrl, outputBasePath, port) {
  return new Promise((resolve) => {
    const args = [
      "lighthouse",
      requestedUrl,
      "--quiet",
      "--only-categories=performance,accessibility,best-practices,seo",
      "--output=json",
      "--output=html",
      `--output-path=${outputBasePath}`,
      `--port=${port}`,
      "--max-wait-for-load=90000",
    ];

    const bin = process.platform === "win32" ? "npx.cmd" : "npx";
    const child = spawn(bin, args, {
      cwd: ROOT_DIR,
      env: process.env,
      shell: false,
    });

    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    child.on("close", (code) => {
      resolve({ code: code ?? 1, stdout, stderr });
    });
  });
}

function evaluateThresholds(group, scores) {
  const threshold = THRESHOLDS[group];
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

async function main() {
  ensureDir(OUTPUT_DIR);

  const manifestRaw = fs.readFileSync(ROUTE_MANIFEST_PATH, "utf8");
  const manifest = JSON.parse(manifestRaw);
  const routes = Array.isArray(manifest.routes) ? manifest.routes : [];
  if (routes.length === 0) {
    throw new Error("Route manifest is empty.");
  }

  const browser = await chromium.launch({
    headless: true,
    args: [
      `--remote-debugging-port=${LIGHTHOUSE_PORT}`,
      "--no-sandbox",
      "--disable-dev-shm-usage",
    ],
  });

  const context = await browser.newContext({ baseURL: BASE_URL });
  const page = await context.newPage();
  const loginState = await loginWithPlaywright(page);

  const results = [];

  for (let index = 0; index < routes.length; index += 1) {
    const routeItem = routes[index];
    const route = resolveRoute(routeItem.path);
    const group = routeItem.group || "internal-auth";
    const requestedUrl = new URL(route, BASE_URL).toString();
    const slug = sanitizeRoute(`${String(index + 1).padStart(2, "0")}-${route}`);
    const outputBasePath = path.resolve(OUTPUT_DIR, `${slug}-${nowStamp}`);

    const run = await runLighthouse(requestedUrl, outputBasePath, LIGHTHOUSE_PORT);
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
        errorSnippet: snippet,
        htmlReport: fs.existsSync(htmlReport) ? htmlReport : null,
        jsonReport: fs.existsSync(jsonReport) ? jsonReport : null,
      });
      continue;
    }

    const lhr = JSON.parse(fs.readFileSync(jsonReport, "utf8"));
    const performance = getCategoryScore(lhr, "performance");
    const accessibility = getCategoryScore(lhr, "accessibility");
    const bestPractices = getCategoryScore(lhr, "best-practices");
    const seo = getCategoryScore(lhr, "seo");

    const thresholdEval = evaluateThresholds(group, {
      performance,
      accessibility,
      bestPractices,
      seo,
    });

    const row = {
      route,
      group,
      requestedUrl,
      finalUrl: lhr?.finalDisplayedUrl || null,
      status: thresholdEval.passed ? "ok" : "threshold_fail",
      classification: thresholdEval.passed ? null : "code",
      performance,
      accessibility,
      bestPractices,
      seo,
      thresholdPassed: thresholdEval.passed,
      failedChecks: thresholdEval.failedChecks,
      errorSnippet: thresholdEval.passed
        ? null
        : `Failed checks: ${thresholdEval.failedChecks.join(", ")}`,
      htmlReport,
      jsonReport,
    };
    results.push(row);
  }

  await context.close();
  await browser.close();

  const aggregate = {
    generatedAt: new Date().toISOString(),
    baseUrl: BASE_URL,
    auditId: PERF_AUDIT_ID,
    login: loginState,
    auditedTotal: results.length,
    ok: results.filter((r) => r.status === "ok").length,
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

  fs.writeFileSync(summaryJsonPath, JSON.stringify(results, null, 2), "utf8");
  fs.writeFileSync(summaryCsvPath, toCsv(results), "utf8");
  fs.writeFileSync(aggregateJsonPath, JSON.stringify(aggregate, null, 2), "utf8");

  const blockingFailures = results.filter((r) => r.status !== "ok");

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

  if (blockingFailures.length > 0) {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error("quality:web:full failed:", error);
  process.exitCode = 1;
});
