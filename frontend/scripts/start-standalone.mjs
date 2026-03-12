#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(SCRIPT_DIR, "..");
const WORKSPACE_ROOT = path.resolve(ROOT_DIR, "..");
const BUILD_DIR = path.resolve(ROOT_DIR, ".next");
const STANDALONE_DIR = path.resolve(BUILD_DIR, "standalone");
const SERVER_ENTRY = path.resolve(STANDALONE_DIR, "server.js");
const STATIC_SOURCE = path.resolve(BUILD_DIR, "static");
const STATIC_TARGET = path.resolve(STANDALONE_DIR, ".next", "static");
const PUBLIC_SOURCE = path.resolve(ROOT_DIR, "public");
const PUBLIC_TARGET = path.resolve(STANDALONE_DIR, "public");
const ENV_FILES = [
  path.resolve(WORKSPACE_ROOT, ".env"),
  path.resolve(ROOT_DIR, ".env"),
];

const syncTree = (source, target) => {
  if (!fs.existsSync(source)) {
    return;
  }

  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.cpSync(source, target, {
    recursive: true,
    force: true,
  });
};

const parseEnvFile = (source) => {
  const entries = {};
  const quotedValuePattern = /^(["'])(?<value>(?:\\.|(?!\1).)*)\1(?:\s+#.*)?$/u;

  for (const line of source.split(/\r?\n/u)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }

    const normalized = trimmed.startsWith("export ")
      ? trimmed.slice("export ".length).trim()
      : trimmed;
    const separatorIndex = normalized.indexOf("=");
    if (separatorIndex <= 0) {
      continue;
    }

    const key = normalized.slice(0, separatorIndex).trim();
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/u.test(key)) {
      continue;
    }

    let value = normalized.slice(separatorIndex + 1).trim();
    const quotedMatch = value.match(quotedValuePattern);
    if (quotedMatch?.groups?.value !== undefined) {
      value = quotedMatch.groups.value;
    } else {
      const inlineCommentIndex = value.indexOf(" #");
      if (inlineCommentIndex >= 0) {
        value = value.slice(0, inlineCommentIndex).trim();
      }
    }

    entries[key] = value.replace(/\\n/g, "\n");
  }

  return entries;
};

const loadEnvFiles = () => {
  for (const envFile of ENV_FILES) {
    if (!fs.existsSync(envFile)) {
      continue;
    }

    const parsed = parseEnvFile(fs.readFileSync(envFile, "utf8"));
    for (const [key, value] of Object.entries(parsed)) {
      if (!(key in process.env)) {
        process.env[key] = value;
      }
    }
  }
};

if (!fs.existsSync(SERVER_ENTRY)) {
  console.error(
    "Standalone server build is missing. Run `pnpm build` before `pnpm start`.",
  );
  process.exit(1);
}

loadEnvFiles();
syncTree(STATIC_SOURCE, STATIC_TARGET);
syncTree(PUBLIC_SOURCE, PUBLIC_TARGET);

const child = spawn(process.execPath, [SERVER_ENTRY], {
  cwd: ROOT_DIR,
  env: process.env,
  stdio: "inherit",
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 0);
});
