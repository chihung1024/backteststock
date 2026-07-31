import { METRIC_DEFINITION_VERSION } from "../public/scan-score-formulas.js";

const originArgument = process.argv[2];

if (!originArgument) {
  throw new Error("Usage: node scripts/smoke_test_production.mjs <worker-origin>");
}

const origin = new URL(originArgument);
const MIN_RUSSELL_MEMBERS = 1_500;
const MIN_FUNDAMENTALS_COVERAGE = 1_000;
const REQUEST_TIMEOUT_MS = 240_000;
const BACKEND_VERSION_ATTEMPTS = 24;
const BACKEND_VERSION_DELAY_MS = 15_000;

function sleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function assertCondition(condition, message) {
  if (!condition) throw new Error(message);
}

async function requestJson(pathname, init = {}, options = {}) {
  const attempts = options.attempts ?? 6;
  const delayMs = options.delayMs ?? 10_000;
  let lastError;

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      const response = await fetch(new URL(pathname, origin), {
        ...init,
        headers: {
          accept: "application/json",
          ...(init.headers || {}),
        },
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });
      const text = await response.text();
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${text.slice(0, 500)}`);
      }
      return JSON.parse(text);
    } catch (error) {
      lastError = error;
      if (attempt === attempts) break;
      console.warn(
        `Production smoke request ${pathname} failed on attempt ${attempt}/${attempts}: ${error.message}`,
      );
      await sleep(delayMs);
    }
  }

  throw new Error(`Production smoke request ${pathname} failed: ${lastError?.message}`);
}

async function waitForBackendMetricVersion() {
  let lastObserved = null;
  let lastError = null;

  for (let attempt = 1; attempt <= BACKEND_VERSION_ATTEMPTS; attempt += 1) {
    try {
      const response = await fetch(new URL("/api/health", origin), {
        headers: { accept: "application/json" },
        signal: AbortSignal.timeout(30_000),
      });
      lastObserved = response.headers.get("x-metric-definition-version");
      if (response.ok && lastObserved === METRIC_DEFINITION_VERSION) {
        return lastObserved;
      }
      lastError = `HTTP ${response.status}, metric=${lastObserved || "missing"}`;
    } catch (error) {
      lastError = error.message;
    }

    console.warn(
      `Backend version not ready on attempt ${attempt}/${BACKEND_VERSION_ATTEMPTS}: `
      + `${lastError}; expected ${METRIC_DEFINITION_VERSION}`,
    );
    if (attempt < BACKEND_VERSION_ATTEMPTS) {
      await sleep(BACKEND_VERSION_DELAY_MS);
    }
  }

  throw new Error(
    `Backend did not expose metric version ${METRIC_DEFINITION_VERSION}; `
    + `last observed ${lastObserved || "missing"}: ${lastError}`,
  );
}

const backendMetricVersion = await waitForBackendMetricVersion();

const edgeHealth = await requestJson("/api/edge-health");
assertCondition(edgeHealth.status === "ok", "Edge health did not report status=ok.");
assertCondition(edgeHealth.backendConfigured === true, "Worker backend origin is not configured.");
assertCondition(
  edgeHealth.universeDatabaseConfigured === true,
  "Worker Universe D1 binding is not configured.",
);

const catalogPayload = await requestJson("/api/v2/universes");
assertCondition(Array.isArray(catalogPayload.data), "Universe catalog data is not an array.");
const russellCatalog = catalogPayload.data.find((item) => item?.id === "russell2000");
assertCondition(russellCatalog?.available === true, "Russell 2000 Universe is unavailable.");
assertCondition(
  Number(russellCatalog.memberCount) >= MIN_RUSSELL_MEMBERS,
  `Russell 2000 catalog contains only ${russellCatalog?.memberCount ?? 0} members.`,
);

const detailPayload = await requestJson("/api/v2/universes/russell2000");
const russellDetail = detailPayload.data;
assertCondition(Array.isArray(russellDetail?.members), "Russell 2000 member detail is missing.");
assertCondition(
  russellDetail.members.length >= MIN_RUSSELL_MEMBERS,
  `Russell 2000 detail contains only ${russellDetail.members.length} members.`,
);
const invalidMembers = russellDetail.members.filter(
  (member) => typeof member?.ticker !== "string" || !member.ticker.trim(),
);
assertCondition(
  invalidMembers.length === 0,
  `${invalidMembers.length} Russell 2000 members do not have a valid ticker.`,
);

const screenerPayload = await requestJson(
  "/api/v2/screener",
  {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      universe: "russell2000",
      sector: "any",
      filters: {},
      sort: "marketCap-desc",
      limit: 10,
    }),
  },
  { attempts: 4, delayMs: 15_000 },
);

assertCondition(Array.isArray(screenerPayload.candidates), "Screener candidates are missing.");
assertCondition(
  screenerPayload.candidates.length === 10,
  `Russell 2000 screener returned ${screenerPayload.candidates.length} candidates instead of 10.`,
);
assertCondition(
  screenerPayload.candidates.every(
    (candidate) => typeof candidate?.ticker === "string" && candidate.ticker.trim(),
  ),
  "Russell 2000 screener returned a candidate without a ticker.",
);
assertCondition(
  Number(screenerPayload.funnel?.fundamentalsAvailable) >= MIN_FUNDAMENTALS_COVERAGE,
  `Russell 2000 fundamentals coverage is only ${screenerPayload.funnel?.fundamentalsAvailable ?? 0}.`,
);

const scanContract = await requestJson(
  "/api/scan",
  {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      tickers: ["AAPL"],
      benchmark: "SPY",
      startYear: 2025,
      startMonth: 1,
      endYear: 2025,
      endMonth: 3,
    }),
  },
  { attempts: 3, delayMs: 15_000 },
);
assertCondition(Array.isArray(scanContract), "Scan endpoint did not return an array.");
assertCondition(scanContract.length === 1, "Scan endpoint did not return the requested AAPL row.");
const scanRow = scanContract[0];
assertCondition(
  scanRow?.ticker === "AAPL" && scanRow.status === "ok" && scanRow.retryable === false,
  `Live scan did not succeed: ${JSON.stringify(scanRow).slice(0, 500)}`,
);
assertCondition(
  scanRow.metric_definition_version === METRIC_DEFINITION_VERSION,
  `Scan metric version ${scanRow.metric_definition_version} does not match ${METRIC_DEFINITION_VERSION}.`,
);
assertCondition(
  Number(scanRow.metric_price_observations) >= 20,
  `Live scan returned only ${scanRow.metric_price_observations ?? 0} price observations.`,
);
assertCondition(scanRow.benchmark_available === true, "SPY benchmark data was unavailable.");
assertCondition(Number.isFinite(scanRow.beta), "Live scan did not calculate Beta.");
assertCondition(Number.isFinite(scanRow.alpha), "Live scan did not calculate Alpha.");
assertCondition(
  scanRow.data_source_settings?.repair === true,
  "Live scan did not use the required yfinance repair=true contract.",
);

console.log(
  JSON.stringify(
    {
      workerOrigin: origin.origin,
      backendMetricVersion,
      universeVersion: russellDetail.version,
      memberCount: russellDetail.members.length,
      fundamentalsAvailable: screenerPayload.funnel.fundamentalsAvailable,
      returnedTickers: screenerPayload.candidates.map((candidate) => candidate.ticker),
      scanContractStatus: scanRow.status,
      scanTicker: scanRow.ticker,
      scanPriceObservations: scanRow.metric_price_observations,
      scanBeta: scanRow.beta,
      scanAlpha: scanRow.alpha,
      scipyVersion: scanRow.scipy_version,
    },
    null,
    2,
  ),
);
