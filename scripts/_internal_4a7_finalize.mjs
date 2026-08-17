import { readFileSync, writeFileSync } from "node:fs";

function replaceOnce(text, before, after, label) {
  const index = text.indexOf(before);
  if (index < 0) throw new Error(`${label} anchor not found`);
  if (text.indexOf(before, index + before.length) >= 0) throw new Error(`${label} anchor is not unique`);
  return `${text.slice(0, index)}${after}${text.slice(index + before.length)}`;
}

const packagePath = "package.json";
const packageJson = JSON.parse(readFileSync(packagePath, "utf8"));
packageJson.devDependencies ??= {};
packageJson.devDependencies["@vitejs/plugin-react"] = "6.0.4";
packageJson.devDependencies = Object.fromEntries(
  Object.entries(packageJson.devDependencies).sort(([left], [right]) => left.localeCompare(right)),
);
writeFileSync(packagePath, `${JSON.stringify(packageJson, null, 2)}\n`);

const panelPath = "apps/portfolio-web/src/ResearchLibraryPanel.tsx";
let panel = readFileSync(panelPath, "utf8");
panel = replaceOnce(
  panel,
  "  const activeController = useRef<AbortController | null>(null);\n  const namePlaceholder = useMemo(() => suggestedRunName(request), [request]);",
  "  const activeController = useRef<AbortController | null>(null);\n  const operationVersion = useRef(0);\n  const namePlaceholder = useMemo(() => suggestedRunName(request), [request]);",
  "operation version ref",
);
panel = replaceOnce(
  panel,
  "  useEffect(() => () => activeController.current?.abort(), []);",
  `  useEffect(() => () => {\n    operationVersion.current += 1;\n    activeController.current?.abort();\n  }, []);`,
  "operation cleanup",
);
panel = replaceOnce(
  panel,
  `    activeController.current?.abort();\n    const controller = new AbortController();\n    activeController.current = controller;\n    setAction(nextAction);`,
  `    activeController.current?.abort();\n    const controller = new AbortController();\n    const version = ++operationVersion.current;\n    activeController.current = controller;\n    setAction(nextAction);`,
  "operation start",
);
panel = replaceOnce(
  panel,
  `    try {\n      return await operation(controller.signal);\n    } catch (caught) {\n      if (!(caught instanceof DOMException && caught.name === "AbortError")) setError(libraryErrorText(caught));\n      return null;\n    } finally {\n      if (activeController.current === controller) activeController.current = null;\n      setAction((current) => current === nextAction ? null : current);\n      onBusyChange(false);\n    }`,
  `    try {\n      const response = await operation(controller.signal);\n      if (version !== operationVersion.current || activeController.current !== controller) return null;\n      return response;\n    } catch (caught) {\n      if (!(caught instanceof DOMException && caught.name === "AbortError")) setError(libraryErrorText(caught));\n      return null;\n    } finally {\n      if (version === operationVersion.current && activeController.current === controller) {\n        activeController.current = null;\n        setAction((current) => current === nextAction ? null : current);\n        onBusyChange(false);\n      }\n    }`,
  "operation completion",
);
panel = replaceOnce(
  panel,
  `  function cancelOperation() {\n    activeController.current?.abort();`,
  `  function cancelOperation() {\n    operationVersion.current += 1;\n    activeController.current?.abort();`,
  "cancel operation",
);
panel = replaceOnce(
  panel,
  `  function forgetDeviceCredential() {\n    activeController.current?.abort();`,
  `  function forgetDeviceCredential() {\n    operationVersion.current += 1;\n    activeController.current?.abort();`,
  "forget credential",
);
panel = replaceOnce(
  panel,
  `<small>job {shortHash(run.jobHash)}{run.sourceRunId ? \` · rerun of \${shortHash(run.sourceRunId)}\` : ""}</small>`,
  `<small>run {shortHash(run.runId)} · job {shortHash(run.jobHash)}{run.sourceRunId ? \` · rerun of \${shortHash(run.sourceRunId)}\` : ""}</small>`,
  "run identity",
);
writeFileSync(panelPath, panel);

const concurrencyPath = "tests/e2e/research_library_concurrency.spec.mjs";
let concurrency = readFileSync(concurrencyPath, "utf8");
const staleMarker = 'test("cancel rejects a late successful response even when transport ignores AbortSignal"';
if (!concurrency.includes(staleMarker)) {
  concurrency += String.raw`

test("cancel rejects a late successful response even when transport ignores AbortSignal", async ({ page }) => {
  await mockBase(page);
  await page.addInitScript(() => {
    const realFetch = window.fetch.bind(window);
    window.__resolveLateResearchSave = null;
    window.fetch = (input, init = {}) => {
      const url = typeof input === "string" ? input : input.url;
      if (url.endsWith("/api/v1/research/runs") && init.method === "POST") {
        return new Promise((resolve) => {
          window.__resolveLateResearchSave = () => resolve(new Response(JSON.stringify({
            contractVersion: "research-run-memory-2026-08-17.1",
            libraryId: "lib_late",
            libraryCapability: "rrl_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            run: {
              runId: "run_44444444-4444-4444-8444-444444444444",
              sourceRunId: null,
              name: "Late result",
              jobHash: "9999999999999999999999999999999999999999999999999999999999999999",
              resultContractVersion: "walk-forward-job-2026-08-15.1",
              decisionCount: 1,
              createdAt: "2026-08-17 05:30:00",
            },
            result: { status: "completed" },
          }), { status: 201, headers: { "content-type": "application/json" } }));
        });
      }
      return realFetch(input, init);
    };
  });

  await openWalkForward(page);
  await page.getByLabel("ResearchRun 研究名稱").fill("Late result");
  await page.getByRole("button", { name: "執行並保存", exact: true }).click();
  await expect(page.getByRole("button", { name: "停止等待" })).toBeVisible();
  await page.getByRole("button", { name: "停止等待" }).click();
  await expect(page.getByText(/伺服器端研究可能仍已完成並保存/u)).toBeVisible();

  await page.evaluate(() => window.__resolveLateResearchSave?.());
  await page.waitForTimeout(100);

  const capability = await page.evaluate(() => localStorage.getItem("backteststock.research-library.capability.v1"));
  expect(capability).toBeNull();
  await expect(page.getByText("新研究庫已建立：請立即備份復原碼")).toHaveCount(0);
  await expect(page.getByText("Late result", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "執行並保存", exact: true })).toBeEnabled();
});
`;
}
writeFileSync(concurrencyPath, concurrency);
