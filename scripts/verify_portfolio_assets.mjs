import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { isDeepStrictEqual } from "node:util";
import path from "node:path";

const PORTFOLIO_ROOT = "public/portfolio";
const PORTFOLIO_ASSETS = `${PORTFOLIO_ROOT}/assets`;

function git(...args) {
  return execFileSync("git", args, { encoding: "utf8" });
}

function normalizeRepoPath(value) {
  return value.replaceAll("\\\\", "/");
}

function normalizeSourcePath(source) {
  return normalizeRepoPath(source).replace(
    /node_modules\/\.pnpm\/[^/]+\/node_modules\//g,
    "node_modules/",
  );
}

function normalizeSourceMap(sourceMap) {
  if (!Array.isArray(sourceMap.sources)) {
    throw new Error("Portfolio JavaScript source map is missing a sources array");
  }

  return {
    ...sourceMap,
    sources: sourceMap.sources.map(normalizeSourcePath),
  };
}

function listWorktreeJavaScriptMaps(root) {
  if (!existsSync(root)) {
    return [];
  }

  const output = [];
  const visit = (current) => {
    for (const entry of readdirSync(current)) {
      const absolute = path.join(current, entry);
      const stats = statSync(absolute);
      if (stats.isDirectory()) {
        visit(absolute);
      } else if (entry.endsWith(".js.map")) {
        output.push(normalizeRepoPath(path.relative(process.cwd(), absolute)));
      }
    }
  };

  visit(root);
  return output.sort();
}

function listCommittedJavaScriptMaps() {
  return git("ls-tree", "-r", "--name-only", "HEAD", "--", PORTFOLIO_ASSETS)
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.endsWith(".js.map"))
    .sort();
}

function assertOnlyJavaScriptMapLayoutDiffs() {
  const status = git(
    "status",
    "--porcelain=v1",
    "--untracked-files=all",
    "--",
    "package-lock.json",
    PORTFOLIO_ROOT,
  );

  const unexpected = status
    .split("\n")
    .filter(Boolean)
    .filter((line) => {
      const repoPath = normalizeRepoPath(line.slice(3).replace(/^.* -> /, ""));
      return !repoPath.endsWith(".js.map");
    });

  if (unexpected.length > 0) {
    console.error("Portfolio build changed committed production assets other than JavaScript source-map install-layout metadata:");
    console.error(unexpected.join("\n"));
    process.exit(1);
  }
}

function compareJavaScriptMaps() {
  const committed = listCommittedJavaScriptMaps();
  const worktree = listWorktreeJavaScriptMaps(PORTFOLIO_ASSETS);

  if (!isDeepStrictEqual(committed, worktree)) {
    console.error("Portfolio JavaScript source-map file set changed.");
    console.error(`Committed: ${JSON.stringify(committed)}`);
    console.error(`Built:     ${JSON.stringify(worktree)}`);
    process.exit(1);
  }

  for (const repoPath of committed) {
    const committedText = git("show", `HEAD:${repoPath}`);
    const builtText = readFileSync(repoPath, "utf8");

    let committedMap;
    let builtMap;
    try {
      committedMap = normalizeSourceMap(JSON.parse(committedText));
      builtMap = normalizeSourceMap(JSON.parse(builtText));
    } catch (error) {
      console.error(`Unable to parse Portfolio JavaScript source map: ${repoPath}`);
      throw error;
    }

    if (!isDeepStrictEqual(committedMap, builtMap)) {
      const changedKeys = Array.from(
        new Set([...Object.keys(committedMap), ...Object.keys(builtMap)]),
      ).filter(
        (key) => !isDeepStrictEqual(committedMap[key], builtMap[key]),
      );
      console.error(`Portfolio JavaScript source map changed semantically: ${repoPath}`);
      console.error(`Changed top-level keys: ${changedKeys.join(", ") || "unknown"}`);
      process.exit(1);
    }
  }
}

assertOnlyJavaScriptMapLayoutDiffs();
compareJavaScriptMaps();
console.log(
  "Portfolio production assets match the committed build; package-manager-only JavaScript source-map paths were normalized for comparison.",
);
