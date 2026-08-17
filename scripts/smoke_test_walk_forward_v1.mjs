const workerOrigin = String(process.argv[2] || process.env.WORKER_ORIGIN || "").replace(/\/$/u, "");
const backendOrigin = String(process.env.BACKEND_ORIGIN || "").replace(/\/$/u, "");
const expectedSha = String(process.env.EXPECTED_DEPLOYMENT_SHA || "").trim();

if (!workerOrigin || !backendOrigin || !expectedSha) {
  console.error("WORKER_ORIGIN, BACKEND_ORIGIN and EXPECTED_DEPLOYMENT_SHA are required.");
  process.exit(2);
}

const DEADLINE_MS = 10 * 60 * 1000;
const POLL_MS = 10_000;

function sleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function readJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

async function waitForAuthority() {
  const deadline = Date.now() + DEADLINE_MS;
  let last = "not attempted";
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${backendOrigin}/api/internal/research/exhaustive-selection`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "cache-control": "no-store",
          "x-backteststock-internal-deployment": expectedSha,
        },
        body: JSON.stringify({ type: "version" }),
      });
      const payload = await readJson(response);
      const returnedSha = response.headers.get("x-backteststock-deployment-sha") || "";
      if (
        response.status === 200
        && returnedSha === expectedSha
        && typeof payload?.authorityVersion === "string"
        && typeof payload?.bridgeVersion === "string"
      ) {
        return payload;
      }
      last = `status=${response.status} sha=${returnedSha || "missing"} body=${JSON.stringify(payload)}`;
    } catch (error) {
      last = error instanceof Error ? error.message : String(error);
    }
    await sleep(POLL_MS);
  }
  throw new Error(`Exhaustive authority did not reach expected deployment ${expectedSha}: ${last}`);
}

async function waitForWalkForwardHealth() {
  const deadline = Date.now() + DEADLINE_MS;
  let last = "not attempted";
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${workerOrigin}/api/v1/research/walk-forward/health`, {
        headers: { "cache-control": "no-store" },
      });
      const payload = await readJson(response);
      const returnedSha = response.headers.get("x-deployment-sha") || payload?.deployment_sha || "";
      if (
        response.status === 200
        && response.headers.get("cache-control")?.includes("no-store")
        && returnedSha === expectedSha
        && payload?.status === "ok"
        && payload?.service === "backteststock-walk-forward-v1"
        && typeof payload?.api_contract_version === "string"
        && typeof payload?.job_contract_version === "string"
      ) {
        return payload;
      }
      last = `status=${response.status} sha=${returnedSha || "missing"} body=${JSON.stringify(payload)}`;
    } catch (error) {
      last = error instanceof Error ? error.message : String(error);
    }
    await sleep(POLL_MS);
  }
  throw new Error(`Walk-Forward health did not reach expected deployment ${expectedSha}: ${last}`);
}

async function readExecutableAdmission() {
  const response = await fetch(`${workerOrigin}/api/v1/research/walk-forward/admission`, {
    headers: { "cache-control": "no-store" },
  });
  const payload = await readJson(response);
  const recommendation = payload?.recommended;
  const universe = Array.isArray(payload?.universes)
    ? payload.universes.find((item) => item?.id === recommendation?.universe)
    : null;
  const valid = response.status === 200
    && response.headers.get("cache-control")?.includes("no-store")
    && response.headers.get("x-walk-forward-admission-contract-version") === payload?.contractVersion
    && typeof payload?.contractVersion === "string"
    && typeof payload?.asOfDate === "string"
    && recommendation
    && universe?.status === "eligible"
    && Number.isInteger(recommendation.holdingCount)
    && recommendation.holdingCount >= 1
    && recommendation.holdingCount <= Number(payload?.limits?.maxHoldingCount)
    && Number.isInteger(recommendation.memberCount)
    && recommendation.memberCount <= Number(payload?.limits?.maxCandidates)
    && Number.isFinite(recommendation.combinationCount)
    && recommendation.combinationCount <= Number(payload?.limits?.maxCombinationsPerPeriod)
    && recommendation.decisionDate >= universe.earliestDecisionDate
    && recommendation.decisionDate <= universe.latestDecisionDate;
  if (!valid) {
    throw new Error(`Walk-Forward admission is not executable: status=${response.status} body=${JSON.stringify(payload)}`);
  }
  return payload;
}

const authority = await waitForAuthority();
const health = await waitForWalkForwardHealth();
const admission = await readExecutableAdmission();
console.log(JSON.stringify({
  status: "ok",
  expectedDeploymentSha: expectedSha,
  authorityVersion: authority.authorityVersion,
  bridgeVersion: authority.bridgeVersion,
  apiContractVersion: health.api_contract_version,
  jobContractVersion: health.job_contract_version,
  admissionContractVersion: admission.contractVersion,
  recommendedUniverse: admission.recommended.universe,
  recommendedDecisionDate: admission.recommended.decisionDate,
  recommendedHoldingCount: admission.recommended.holdingCount,
  recommendedCombinationCount: admission.recommended.combinationCount,
}));
