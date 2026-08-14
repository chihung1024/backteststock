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
const EXPECTED_TWD_VALUATION_CONTRACT = "twd-adjusted-close-union-calendar-2026-08-03.2";

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
  let lastTwdContract = null;
  let lastError = null;

  for (let attempt = 1; attempt <= BACKEND_VERSION_ATTEMPTS; attempt += 1) {
    try {
      const response = await fetch(new URL("/api/health", origin), {
        headers: { accept: "application/json" },
        signal: AbortSignal.timeout(30_000),
      });
      lastObserved = response.headers.get("x-metric-definition-version");
      lastTwdContract = response.headers.get("x-twd-valuation-contract-version");
      if (
        response.ok
        && lastObserved === METRIC_DEFINITION_VERSION
        && lastTwdContract === EXPECTED_TWD_VALUATION_CONTRACT
      ) {
        return { metricVersion: lastObserved, twdContract: lastTwdContract };
      }
      lastError = [
        `HTTP ${response.status}`,
        `metric=${lastObserved || "missing"}`,
        `twd=${lastTwdContract || "missing"}`,
      ].join(", ");
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
    + `TWD contract ${EXPECTED_TWD_VALUATION_CONTRACT}; last observed `
    + `${lastObserved || "missing"}/${lastTwdContract || "missing"}: ${lastError}`,
  );
}

const backendContract = await waitForBackendMetricVersion();

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
assertCondition(
  /^\d{4}-\d{2}-\d{2}$/u.test(String(russellCatalog.sourceAsOf || "")),
  "Russell 2000 catalog is missing a sourceAsOf date required for PIT verification.",
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

const pitDetailPayload = await requestJson(
  `/api/v2/universes/russell2000?asOf=${encodeURIComponent(russellCatalog.sourceAsOf)}`,
);
const pitDetail = pitDetailPayload.data;
assertCondition(pitDetail?.pointInTime === true, "PIT Universe detail is not marked point-in-time.");
assertCondition(
  pitDetail?.requestedAsOf === russellCatalog.sourceAsOf,
  "PIT Universe detail did not preserve requestedAsOf.",
);
assertCondition(
  pitDetail?.sourceAsOf === russellCatalog.sourceAsOf,
  "PIT Universe detail did not resolve the current source observation date.",
);
assertCondition(
  pitDetail?.membershipPolicy === "latest-observed-on-or-before-max-10d-v1",
  "PIT Universe detail returned the wrong membership policy.",
);
assertCondition(
  Array.isArray(pitDetail?.members) && pitDetail.members.length === russellDetail.members.length,
  "PIT Universe archive member count does not match the active snapshot.",
);

const pitScreenerPayload = await requestJson(
  "/api/v2/screener",
  {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      universe: "russell2000",
      selectionAsOf: russellCatalog.sourceAsOf,
      sector: "any",
      filters: {},
      sort: "ticker-asc",
      limit: 3,
    }),
  },
);
assertCondition(
  Array.isArray(pitScreenerPayload.candidates) && pitScreenerPayload.candidates.length === 3,
  "PIT membership screener did not return the requested bounded candidate set.",
);
assertCondition(
  pitScreenerPayload.fundamentalsAsOf === null,
  "PIT membership-only screener unexpectedly reported fundamentals provenance.",
);
assertCondition(
  pitScreenerPayload.researchValidity?.selectionMode === "point_in_time_membership_only"
    && pitScreenerPayload.researchValidity?.membershipPointInTime === true
    && pitScreenerPayload.researchValidity?.fundamentalsApplied === false
    && pitScreenerPayload.researchValidity?.historicalSelectionSafe === true,
  "PIT membership screener research-validity contract is incomplete.",
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
assertCondition(
  screenerPayload.researchValidity?.selectionMode === "current_snapshot_retrospective"
    && screenerPayload.researchValidity?.membershipPointInTime === false
    && screenerPayload.researchValidity?.fundamentalsPointInTime === false
    && screenerPayload.researchValidity?.historicalSelectionSafe === false,
  "Current screener did not disclose its retrospective research-validity boundary.",
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

const exhaustiveContract = await requestJson(
  "/api/optimizer/exhaustive/prepare",
  {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      sourceTickers: ["AAPL", "MSFT"],
      holdingCount: 1,
      benchmark: "SPY",
      startDate: "2025-01-02",
      endDate: "2025-03-31",
    }),
  },
  { attempts: 4, delayMs: 15_000 },
);
assertCondition(
  exhaustiveContract?.summary?.valuationCurrency === "TWD",
  "Exhaustive preflight did not report TWD valuation.",
);
assertCondition(
  exhaustiveContract?.summary?.twdValuationContractVersion
    === EXPECTED_TWD_VALUATION_CONTRACT,
  "Exhaustive preflight returned the wrong TWD valuation contract.",
);
assertCondition(
  exhaustiveContract?.summary?.sourceTickerCount === 2
    && exhaustiveContract?.summary?.holdingCount === 1
    && exhaustiveContract?.summary?.combinationCount === 2,
  "Exhaustive preflight did not preserve the requested 2 choose 1 search shape.",
);
assertCondition(
  typeof exhaustiveContract?.snapshot?.datasetHash === "string"
    && exhaustiveContract.snapshot.datasetHash.length === 64,
  "Exhaustive preflight did not return a signed dataset hash.",
);

console.log(
  JSON.stringify(
    {
      workerOrigin: origin.origin,
      backendMetricVersion: backendContract.metricVersion,
      twdValuationContractVersion: backendContract.twdContract,
      universeVersion: russellDetail.version,
      memberCount: russellDetail.members.length,
      pitSourceAsOf: pitDetail.sourceAsOf,
      pitMemberCount: pitDetail.members.length,
      pitSelectedTickers: pitScreenerPayload.candidates.map((candidate) => candidate.ticker),
      fundamentalsAvailable: screenerPayload.funnel.fundamentalsAvailable,
      returnedTickers: screenerPayload.candidates.map((candidate) => candidate.ticker),
      scanContractStatus: scanRow.status,
      scanTicker: scanRow.ticker,
      scanPriceObservations: scanRow.metric_price_observations,
      scanBeta: scanRow.beta,
      scanAlpha: scanRow.alpha,
      exhaustiveCombinationCount: exhaustiveContract.summary.combinationCount,
      scipyVersion: scanRow.scipy_version,
    },
    null,
    2,
  ),
);