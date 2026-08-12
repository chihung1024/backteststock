import assert from "node:assert/strict";
import test from "node:test";

import {
  normalizeScanJob,
  normalizeScanPayloadDates,
} from "../public/scan-job-normalizer.js";

const fallback = Object.freeze({
  startDate: "2016-08-12",
  endDate: "2026-08-11",
});

test("canonical scan dates remain authoritative", () => {
  const payload = {
    tickers: ["AAA"],
    startDate: "2025-02-03",
    endDate: "2025-07-18",
  };
  assert.deepEqual(normalizeScanPayloadDates(payload, fallback), {
    ...payload,
    startYear: 2025,
    startMonth: 2,
    endYear: 2025,
    endMonth: 7,
  });
});

test("legacy year/month scan dates migrate to the canonical interval", () => {
  assert.deepEqual(
    normalizeScanPayloadDates({
      benchmark: "QQQ",
      startYear: 2025,
      startMonth: 1,
      endYear: 2025,
      endMonth: 12,
    }, fallback),
    {
      benchmark: "QQQ",
      startYear: 2025,
      startMonth: 1,
      endYear: 2025,
      endMonth: 12,
      startDate: "2025-01-01",
      endDate: "2025-12-31",
    },
  );
});

test("legacy future month end is capped by the caller-supplied rolling range", () => {
  const normalized = normalizeScanPayloadDates({
    startYear: 2026,
    startMonth: 7,
    endYear: 2026,
    endMonth: 8,
  }, fallback);
  assert.equal(normalized.startDate, "2026-07-01");
  assert.equal(normalized.endDate, "2026-08-11");
});

test("missing dates use caller fallback without hidden time or storage access", () => {
  const normalized = normalizeScanPayloadDates({ tickers: ["AAA"] }, fallback);
  assert.equal(normalized.startDate, fallback.startDate);
  assert.equal(normalized.endDate, fallback.endDate);
});

test("scan job normalization is immutable and preserves job provenance", () => {
  const job = {
    version: 3,
    id: "legacy-job",
    payload: {
      tickers: ["AAA", "BBB"],
      startYear: 2025,
      startMonth: 1,
      endYear: 2025,
      endMonth: 12,
    },
  };
  const normalized = normalizeScanJob(job, fallback);
  assert.notEqual(normalized, job);
  assert.notEqual(normalized.payload, job.payload);
  assert.equal(normalized.id, "legacy-job");
  assert.equal(normalized.payload.startDate, "2025-01-01");
  assert.equal(job.payload.startDate, undefined);
});

test("invalid fallback fails before producing ambiguous provenance", () => {
  assert.throws(
    () => normalizeScanPayloadDates({}, { startDate: "bad", endDate: "2026-08-11" }),
    /fallbackRange/,
  );
});
