function daysInMonth(year, month) {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

function isValidIsoDate(value) {
  const raw = String(value || "").trim();
  if (!/^\d{4}-\d{2}-\d{2}$/u.test(raw)) return false;
  const [year, month, day] = raw.split("-").map(Number);
  return Number.isInteger(year)
    && Number.isInteger(month)
    && Number.isInteger(day)
    && month >= 1
    && month <= 12
    && day >= 1
    && day <= daysInMonth(year, month);
}

function normalizedFallbackRange(fallbackRange) {
  const startDate = String(fallbackRange?.startDate || "").trim();
  const endDate = String(fallbackRange?.endDate || "").trim();
  if (!isValidIsoDate(startDate) || !isValidIsoDate(endDate) || startDate > endDate) {
    throw new TypeError("fallbackRange must contain a valid startDate/endDate range");
  }
  return { startDate, endDate };
}

function scanPayloadDate(payload, boundary, fallbackRange) {
  const dateKey = boundary === "start" ? "startDate" : "endDate";
  const direct = String(payload?.[dateKey] || "").trim();
  if (isValidIsoDate(direct)) return direct;

  const yearKey = boundary === "start" ? "startYear" : "endYear";
  const monthKey = boundary === "start" ? "startMonth" : "endMonth";
  const year = Number(payload?.[yearKey]);
  const month = Number(payload?.[monthKey]);
  if (Number.isInteger(year) && Number.isInteger(month) && month >= 1 && month <= 12) {
    const day = boundary === "start" ? 1 : daysInMonth(year, month);
    const candidate = [
      year,
      String(month).padStart(2, "0"),
      String(day).padStart(2, "0"),
    ].join("-");
    if (boundary === "end" && candidate > fallbackRange.endDate) {
      return fallbackRange.endDate;
    }
    return candidate;
  }
  return boundary === "start" ? fallbackRange.startDate : fallbackRange.endDate;
}

export function normalizeScanPayloadDates(payload, fallbackRange) {
  const fallback = normalizedFallbackRange(fallbackRange);
  const startDate = scanPayloadDate(payload, "start", fallback);
  const endDate = scanPayloadDate(payload, "end", fallback);
  const [startYear, startMonth] = startDate.split("-").map(Number);
  const [endYear, endMonth] = endDate.split("-").map(Number);
  return {
    ...(payload && typeof payload === "object" ? payload : {}),
    startDate,
    endDate,
    startYear,
    startMonth,
    endYear,
    endMonth,
  };
}

export function normalizeScanJob(job, fallbackRange) {
  if (!job || typeof job !== "object") return job ?? null;
  return {
    ...job,
    payload: normalizeScanPayloadDates(job.payload, fallbackRange),
  };
}
