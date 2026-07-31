const originArgument = process.argv[2];

if (!originArgument) {
  throw new Error("Usage: node scripts/smoke_test_production.mjs <worker-origin>");
}

const origin = new URL(originArgument);
const MIN_RUSSELL_MEMBERS = 1_500;
const MIN_FUNDAMENTALS_COVERAGE = 1_000;
const REQUEST_TIMEOUT_MS = 240_000;

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

console.log(
  JSON.stringify(
    {
      workerOrigin: origin.origin,
      universeVersion: russellDetail.version,
      memberCount: russellDetail.members.length,
      fundamentalsAvailable: screenerPayload.funnel.fundamentalsAvailable,
      returnedTickers: screenerPayload.candidates.map((candidate) => candidate.ticker),
    },
    null,
    2,
  ),
);
