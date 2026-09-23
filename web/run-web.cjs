const { spawn } = require("node:child_process");
const path = require("node:path");
const fs = require("node:fs");

function loadEnv(file) {
  if (!fs.existsSync(file)) return;
  for (const line of fs.readFileSync(file, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq < 0) continue;
    const key = trimmed.slice(0, eq).trim();
    let value = trimmed.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    const comment = value.indexOf(" #");
    if (comment >= 0) value = value.slice(0, comment).trim();
    if (process.env[key] === undefined) process.env[key] = value;
  }
}

loadEnv(path.join(__dirname, "..", ".env"));

const host = process.env.WEB_HOST || "127.0.0.1";
const port = process.env.WEB_PORT || "3000";
const nextBin = path.join(__dirname, "node_modules", "next", "dist", "bin", "next");

const child = spawn(
  process.execPath,
  [nextBin, "start", "--hostname", host, "--port", String(port)],
  { cwd: __dirname, stdio: "inherit", env: process.env },
);

child.on("exit", (code) => process.exit(code ?? 0));
