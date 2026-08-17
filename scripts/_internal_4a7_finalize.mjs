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
