import fs from "node:fs";
import path from "node:path";
import type { NextConfig } from "next";

function loadRootEnv() {
  const envPath = path.join(__dirname, "..", ".env");
  if (!fs.existsSync(envPath)) return;
  for (const line of fs.readFileSync(envPath, "utf8").split(/\r?\n/)) {
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

loadRootEnv();

function apiInternalUrl() {
  return (
    process.env.API_INTERNAL_URL ||
    `http://127.0.0.1:${process.env.API_PORT || process.env.LYNOTE_API_PORT || "8000"}`
  );
}

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: path.join(__dirname),
  experimental: {
    middlewareClientMaxBodySize: "32mb",
  },
  async rewrites() {
    return [
      {
        source: "/v1/:path*",
        destination: `${apiInternalUrl()}/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
