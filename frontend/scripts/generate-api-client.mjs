import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(frontendRoot, "..");
const backendPath = path.resolve(repoRoot, "backend");

const openApiJsonPath = path.resolve(
  frontendRoot,
  "lib",
  "api-client",
  "openapi.json",
);
const outputTypesPath = path.resolve(
  frontendRoot,
  "lib",
  "api-client",
  "schema.ts",
);

const pythonSource = `
import json
import pathlib
import sys

from app.main import create_app

output = pathlib.Path(sys.argv[1])
output.parent.mkdir(parents=True, exist_ok=True)
app = create_app()
output.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
print(f"OpenAPI schema written to {output}")
`;

const pythonResult = spawnSync("python", ["-c", pythonSource, openApiJsonPath], {
  cwd: repoRoot,
  env: { ...process.env, PYTHONPATH: backendPath },
  stdio: "inherit",
});

if (pythonResult.status !== 0) {
  process.exit(pythonResult.status ?? 1);
}

const typesResult = spawnSync(
  "pnpm",
  ["exec", "openapi-typescript", openApiJsonPath, "-o", outputTypesPath],
  {
    cwd: frontendRoot,
    stdio: "inherit",
    shell: process.platform === "win32",
  },
);

if (typesResult.error) {
  console.error(typesResult.error);
  process.exit(1);
}

if (typesResult.status !== 0) {
  process.exit(typesResult.status ?? 1);
}

console.log(`Typed API schema generated at ${outputTypesPath}`);
