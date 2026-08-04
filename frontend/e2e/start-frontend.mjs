import { cpSync, existsSync } from "node:fs";
import { spawn } from "node:child_process";
import { resolve } from "node:path";

// Next's standalone output intentionally excludes static/public assets. Copy
// them beside the generated server so E2E covers the same production entry
// point as the container image, including client-side form hydration.
const standalone = resolve(".next/standalone/frontend");
const staticSource = resolve(".next/static");
const staticTarget = resolve(standalone, ".next/static");
if (!existsSync(standalone) || !existsSync(staticSource)) {
  throw new Error("Missing Next standalone build. Run `pnpm --filter frontend build` before E2E tests.");
}
cpSync(staticSource, staticTarget, { recursive: true, force: true });

const publicSource = resolve("public");
if (existsSync(publicSource)) cpSync(publicSource, standalone, { recursive: true, force: true });

const child = spawn(process.execPath, [resolve(standalone, "server.js")], { stdio: "inherit", env: process.env });
child.on("exit", (code) => process.exit(code ?? 1));
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
