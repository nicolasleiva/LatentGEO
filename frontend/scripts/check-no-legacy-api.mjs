import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendRoot = path.resolve(__dirname, "..");

const scopes = [
  "app",
  "components",
  "hooks",
  "lib",
  "__tests__",
  "e2e",
].map((relative) => path.join(frontendRoot, relative));

const excludedPathFragments = [path.join("lib", "api-client")];
const legacyApiPattern = /\/api\/(?!v1\/|auth(?:\/|$)|sse(?:\/|$))/g;

function walk(dir) {
  const entries = readdirSync(dir, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    const normalizedPath = fullPath.replaceAll("\\", "/");

    if (
      excludedPathFragments.some((fragment) =>
        normalizedPath.includes(fragment.replaceAll("\\", "/")),
      )
    ) {
      continue;
    }

    if (entry.isDirectory()) {
      files.push(...walk(fullPath));
      continue;
    }

    if (!entry.isFile()) {
      continue;
    }

    if (entry.name.endsWith(".md")) {
      continue;
    }

    files.push(fullPath);
  }

  return files;
}

const violations = [];

for (const scopeDir of scopes) {
  if (!statSync(scopeDir, { throwIfNoEntry: false })?.isDirectory()) {
    continue;
  }
  for (const filePath of walk(scopeDir)) {
    const content = readFileSync(filePath, "utf8");
    const lines = content.split(/\r?\n/);

    lines.forEach((line, index) => {
      legacyApiPattern.lastIndex = 0;
      if (legacyApiPattern.test(line)) {
        const relativePath = path.relative(frontendRoot, filePath).replaceAll("\\", "/");
        violations.push(`${relativePath}:${index + 1}: ${line.trim()}`);
      }
    });
  }
}

if (violations.length > 0) {
  console.error("Legacy backend API paths detected. Use /api/v1/* instead.");
  for (const violation of violations) {
    console.error(`- ${violation}`);
  }
  process.exit(1);
}

console.log("No legacy backend /api/* paths found in frontend runtime/tests.");
