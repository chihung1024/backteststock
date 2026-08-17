const WALK_FORWARD_ADMISSION_PATH = "/api/v1/research/walk-forward/admission";
const WALK_FORWARD_ADMISSION_CONTRACT_VERSION = "walk-forward-admission-2026-08-17.1";
const MAX_CANDIDATES = 100;
const MAX_COMBINATIONS_PER_PERIOD = 500_000;
const MAX_HOLDING_COUNT = 20;
const PIT_MAX_AGE_DAYS = 10;
const DAY_MS = 24 * 60 * 60 * 1000;

function jsonResponse(payload, status, requestId) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
      "x-request-id": requestId,
      "x-walk-forward-admission-contract-version": WALK_FORWARD_ADMISSION_CONTRACT_VERSION,
    },
  });
}

function isoDate(value) {
  const raw = String(value || "").slice(0, 10);
  const timestamp = Date.parse(`${raw}T00:00:00Z`);
  if (!/^\d{4}-\d{2}-\d{2}$/u.test(raw) || !Number.isFinite(timestamp)) return null;
  if (new Date(timestamp).toISOString().slice(0, 10) !== raw) return null;
  return { raw, timestamp };
}

function latestCompleteUtcDate() {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() - 1);
  return date.toISOString().slice(0, 10);
}

function combinationCount(n, k) {
  if (!Number.isSafeInteger(n) || !Number.isSafeInteger(k) || n < 0 || k < 0 || k > n) {
    return Number.POSITIVE_INFINITY;
  }
  const effective = Math.min(k, n - k);
  let result = 1;
  for (let index = 1; index <= effective; index += 1) {
    result = (result * (n - effective + index)) / index;
    if (!Number.isSafeInteger(result) || result > MAX_COMBINATIONS_PER_PERIOD) return result;
  }
  return result;
}

function recommendedHoldingCount(memberCount) {
  for (let holding = Math.min(10, MAX_HOLDING_COUNT, memberCount); holding >= 1; holding -= 1) {
    if (combinationCount(memberCount, holding) <= MAX_COMBINATIONS_PER_PERIOD) return holding;
  }
  return null;
}

function eligibleDecisionWindow(row, asOfDate) {
  const source = isoDate(row.source_as_of);
  const fetched = isoDate(row.fetched_at);
  const asOf = isoDate(asOfDate);
  if (!source || !fetched || !asOf) return null;
  const lagDays = Math.floor((fetched.timestamp - source.timestamp) / DAY_MS);
  if (lagDays < 0 || lagDays > PIT_MAX_AGE_DAYS) return null;
  const startTimestamp = Math.max(source.timestamp, fetched.timestamp);
  const endTimestamp = Math.min(source.timestamp + PIT_MAX_AGE_DAYS * DAY_MS, asOf.timestamp);
  // Evaluation must begin strictly after Decision, so Decision cannot consume the final complete day.
  if (startTimestamp >= endTimestamp) return null;
  return {
    start: new Date(startTimestamp).toISOString().slice(0, 10),
    end: new Date(endTimestamp).toISOString().slice(0, 10),
    memberCount: Number(row.member_count),
    sourceAsOf: source.raw,
    fetchedDate: fetched.raw,
    version: String(row.version || ""),
  };
}

function summarizeUniverse(universe, snapshots, asOfDate) {
  if (!snapshots.length) {
    return { id: universe.id, name: universe.name, status: "blocked", reason: "no_pit_snapshots" };
  }
  const authoritative = snapshots.filter((row) => !Boolean(row.is_proxy));
  if (!authoritative.length) {
    return { id: universe.id, name: universe.name, status: "blocked", reason: "proxy_membership_only" };
  }
  const bounded = authoritative.filter((row) => Number(row.member_count) <= MAX_CANDIDATES);
  if (!bounded.length) {
    return {
      id: universe.id,
      name: universe.name,
      status: "blocked",
      reason: "candidate_limit",
      minimumMemberCount: Math.min(...authoritative.map((row) => Number(row.member_count))),
    };
  }
  const windows = bounded
    .map((row) => eligibleDecisionWindow(row, asOfDate))
    .filter(Boolean)
    .sort((left, right) => left.start.localeCompare(right.start));
  if (!windows.length) {
    return { id: universe.id, name: universe.name, status: "blocked", reason: "no_causal_snapshot_window" };
  }
  const first = windows[0];
  const last = windows.reduce((best, window) => window.end > best.end ? window : best, windows[0]);
  const holdingCount = recommendedHoldingCount(first.memberCount);
  if (!holdingCount) {
    return { id: universe.id, name: universe.name, status: "blocked", reason: "combination_budget" };
  }
  return {
    id: universe.id,
    name: universe.name,
    status: "eligible",
    earliestDecisionDate: first.start,
    latestDecisionDate: last.end,
    recommendedDecisionDate: first.start,
    recommendedMemberCount: first.memberCount,
    recommendedHoldingCount: holdingCount,
    recommendedCombinationCount: combinationCount(first.memberCount, holdingCount),
    sourceAsOf: first.sourceAsOf,
    evidenceAvailableAsOf: first.fetchedDate,
    version: first.version,
  };
}

async function getWalkForwardAdmission(env, requestId) {
  if (!env.DB) {
    return jsonResponse({ error: "Walk-Forward admission database is not configured." }, 503, requestId);
  }
  const asOfDate = latestCompleteUtcDate();
  try {
    const universesResult = await env.DB.prepare(
      `SELECT id, name, sort_order
       FROM universes
       WHERE enabled = 1
       ORDER BY sort_order, id`,
    ).all();
    const snapshotsResult = await env.DB.prepare(
      `SELECT universe_id, source_as_of, fetched_at, member_count, is_proxy, version
       FROM universe_snapshot_archive
       ORDER BY universe_id, fetched_at, source_as_of`,
    ).all();
    const byUniverse = new Map();
    for (const row of snapshotsResult.results) {
      const rows = byUniverse.get(row.universe_id) || [];
      rows.push(row);
      byUniverse.set(row.universe_id, rows);
    }
    const universes = universesResult.results.map((universe) =>
      summarizeUniverse(universe, byUniverse.get(universe.id) || [], asOfDate));
    const recommendedUniverse = universes.find((item) => item.status === "eligible") || null;
    const recommended = recommendedUniverse
      ? {
          universe: recommendedUniverse.id,
          decisionDate: recommendedUniverse.recommendedDecisionDate,
          holdingCount: recommendedUniverse.recommendedHoldingCount,
          memberCount: recommendedUniverse.recommendedMemberCount,
          combinationCount: recommendedUniverse.recommendedCombinationCount,
        }
      : null;
    return jsonResponse(
      {
        contractVersion: WALK_FORWARD_ADMISSION_CONTRACT_VERSION,
        asOfDate,
        limits: {
          maxCandidates: MAX_CANDIDATES,
          maxCombinationsPerPeriod: MAX_COMBINATIONS_PER_PERIOD,
          maxHoldingCount: MAX_HOLDING_COUNT,
          pitMaxAgeDays: PIT_MAX_AGE_DAYS,
        },
        universes,
        recommended,
      },
      200,
      requestId,
    );
  } catch (error) {
    console.error("Walk-Forward admission query failed", { requestId, message: String(error) });
    return jsonResponse({ error: "Walk-Forward admission evidence is temporarily unavailable." }, 503, requestId);
  }
}

export {
  WALK_FORWARD_ADMISSION_CONTRACT_VERSION,
  WALK_FORWARD_ADMISSION_PATH,
  combinationCount,
  getWalkForwardAdmission,
  recommendedHoldingCount,
  summarizeUniverse,
};
