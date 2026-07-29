#!/usr/bin/env node

const targetName = process.argv[2];
if (!targetName) throw new Error("Provide the D1 database name.");

let input = "";
for await (const chunk of process.stdin) input += chunk;
const payload = JSON.parse(input);
const databases = Array.isArray(payload)
  ? payload
  : payload.result || payload.databases || payload.d1_databases || [];
const match = databases.find((database) => database.name === targetName);
const id = match?.uuid || match?.id;
if (id) process.stdout.write(String(id));
