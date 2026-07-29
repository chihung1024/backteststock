#!/usr/bin/env node

import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

const databaseId = String(process.env.D1_DATABASE_ID || "").trim();
if (!/^[0-9a-f-]{36}$/i.test(databaseId)) {
  throw new Error("D1_DATABASE_ID must be a Cloudflare D1 UUID.");
}

const sourcePath = resolve(process.argv[2] || "wrangler.jsonc");
const outputPath = resolve(process.argv[3] || "wrangler.production.jsonc");
const config = JSON.parse(await readFile(sourcePath, "utf8"));
const binding = config.d1_databases?.find((item) => item.binding === "DB");
if (!binding) throw new Error("wrangler.jsonc is missing the DB D1 binding.");

binding.database_id = databaseId;
await mkdir(dirname(outputPath), { recursive: true });
await writeFile(outputPath, `${JSON.stringify(config, null, 2)}\n`);
console.log(`Rendered ${outputPath} for D1 database ${databaseId}.`);
