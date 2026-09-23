const { spawn } = require("node:child_process");
const path = require("node:path");
const fs = require("node:fs");

const root = __dirname;
const isWin = process.platform === "win32";
const python = isWin
  ? path.join(root, ".venv", "Scripts", "python.exe")
  : path.join(root, ".venv", "bin", "python");

if (process.argv.includes("--install")) {
  const pip = spawn(python, ["-m", "pip", "install", "-e", "."], {
    cwd: root,
    stdio: "inherit",
  });
  pip.on("exit", (code) => process.exit(code ?? 0));
  return;
}

if (!fs.existsSync(python)) {
  console.error(
    "Backend venv missing. From backend/: python -m venv .venv && node ./run-api.cjs --install",
  );
  process.exit(1);
}

const child = spawn(python, ["-m", "lynote"], { cwd: root, stdio: "inherit" });

child.on("exit", (code) => process.exit(code ?? 0));
