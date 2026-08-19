const TICKER_PATTERN = /^[A-Z0-9.^=_-]{1,20}$/u;
const ISHARES_DATE_PATTERN = /Fund Holdings as of,"([^"]+)"/u;
const RETRYABLE_STATUS = new Set([429, 500, 502, 503, 504]);
const MAX_RETAINED_VERSIONS = 12;
const NASDAQ_GIW_SOURCE_URL = "https://indexes.nasdaq.com/Index/Weighting/NDX";
const NASDAQ_GIW_DATA_URL = "https://indexes.nasdaq.com/Index/WeightingData";
const NASDAQ_GIW_LOOKBACK_WEEKDAYS = 7;
const INVESCO_QQQM_HOLDINGS_URL =
  "https://dng-api.invesco.com/cache/v1/accounts/en_US/shareclasses/46138G649/holdings/fund?idType=cusip&productType=ETF";

const TICKER_ALIASES = Object.freeze({
  BRKA: "BRK-A",
  BRKB: "BRK-B",
  BFA: "BF-A",
  BFB: "BF-B",
});

export class UniverseUpdateError extends Error {}

function sourceDefinitions(env = {}) {
  return [
    {
      id: "sp500",
      name: "S&P 500（IVV holdings）",
      sourceLabel: "iShares IVV holdings",
      sourceUrl:
        env.UNIVERSE_SP500_URL ||
        "https://www.ishares.com/us/products/239726/ishares-core-s-p-500-etf/latest-holdings.csv",
      adapter: "ishares_csv",
      minMembers: 480,
      maxMembers: 530,
      maxCountChangeRatio: 0.08,
      maxMembershipChurnRatio: 0.10,
      isProxy: true,
      proxyNote:
        "此清單是 IVV 公開持股代理池，可能包含現金、衍生品差異或與正式 S&P 500 授權名單存在短暫時差。",
    },
    {
      id: "nasdaq100",
      name: "NASDAQ-100",
      sourceLabel: "Nasdaq Global Index Watch",
      sourceUrl: NASDAQ_GIW_SOURCE_URL,
      fetchUrl: env.UNIVERSE_NASDAQ100_GIW_URL || NASDAQ_GIW_DATA_URL,
      adapter: "nasdaq_giw_json",
      minMembers: 95,
      maxMembers: 110,
      maxCountChangeRatio: 0.12,
      maxMembershipChurnRatio: 0.15,
      fallbacks: [
        {
          sourceLabel: "Nasdaq official API",
          sourceUrl:
            env.UNIVERSE_NASDAQ100_URL ||
            "https://api.nasdaq.com/api/quote/list-type/nasdaq100",
          adapter: "nasdaq_json",
        },
        {
          sourceLabel: "Invesco QQQM holdings",
          sourceUrl:
            env.UNIVERSE_NASDAQ100_FALLBACK_URL || INVESCO_QQQM_HOLDINGS_URL,
          adapter: "invesco_json",
          isProxy: true,
          proxyNote:
            "Nasdaq 官方 API 本次不可用，已使用追蹤 Nasdaq-100 的 Invesco QQQM 公開持股代理池；可能存在追蹤誤差或調整時差。",
        },
      ],
    },
    {
      id: "soxx",
      name: "SOXX holdings",
      sourceLabel: "iShares SOXX holdings",
      sourceUrl:
        env.UNIVERSE_SOXX_URL ||
        "https://www.ishares.com/us/products/239705/ishares-semiconductor-etf/latest-holdings.csv",
      adapter: "ishares_csv",
      minMembers: 25,
      maxMembers: 40,
      maxCountChangeRatio: 0.30,
      maxMembershipChurnRatio: 0.35,
    },
    {
      id: "russell2000",
      name: "Russell 2000（IWM holdings 代理）",
      sourceLabel: "iShares IWM holdings",
      sourceUrl:
        env.UNIVERSE_RUSSELL2000_URL ||
        "https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/latest-holdings.csv",
      adapter: "ishares_csv",
      minMembers: 1750,
      maxMembers: 2100,
      maxCountChangeRatio: 0.10,
      maxMembershipChurnRatio: 0.15,
      isProxy: true,
      proxyNote:
        "此清單是 IWM 公開持股代理池，不是 FTSE Russell 授權的正式指數成分名單，可能有追蹤誤差與調整時差。",
    },
  ];
}

function endpointFrom(source) {
  return {
    sourceLabel: source.sourceLabel,
    sourceUrl: source.sourceUrl,
    fetchUrl: source.fetchUrl,
    adapter: source.adapter,
    isProxy: Boolean(source.isProxy),
    proxyNote: source.proxyNote || null,
  };
}

function nowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/u, "Z");
}

export function normalizeTicker(rawValue) {
  const source = String(rawValue || "").trim().toUpperCase();
  if (!source) throw new UniverseUpdateError("empty ticker");
  const normalized = TICKER_ALIASES[source] || source.replaceAll(".", "-");
  if (!TICKER_PATTERN.test(normalized)) {
    throw new UniverseUpdateError(`invalid ticker: ${source}`);
  }
  return normalized;
}

function cleanText(value) {
  const text = String(value ?? "").trim();
  return text || null;
}

function optionalFloat(value) {
  const text = String(value ?? "").replaceAll(",", "").replaceAll("%", "").trim();
  if (!text || text === "-") return null;
  const numeric = Number(text);
  return Number.isFinite(numeric) ? numeric : null;
}

export function isoDate(rawValue) {
  const raw = String(rawValue || "").trim();
  if (!raw) return null;
  let year;
  let month;
  let day;
  let match = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/u);
  if (match) {
    [, year, month, day] = match;
  } else if ((match = raw.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/u))) {
    month = match[1].padStart(2, "0");
    day = match[2].padStart(2, "0");
    year = match[3];
  } else {
    const parsed = Date.parse(`${raw} 00:00:00 GMT`);
    if (!Number.isFinite(parsed)) {
      throw new UniverseUpdateError(`unsupported source date: ${raw}`);
    }
    return new Date(parsed).toISOString().slice(0, 10);
  }
  const candidate = `${year}-${month}-${day}`;
  const parsed = Date.parse(`${candidate}T00:00:00Z`);
  if (!Number.isFinite(parsed) || new Date(parsed).toISOString().slice(0, 10) !== candidate) {
    throw new UniverseUpdateError(`unsupported source date: ${raw}`);
  }
  return candidate;
}

export function validateSourceDate(sourceId, sourceAsOf, now = new Date()) {
  if (!sourceAsOf) {
    throw new UniverseUpdateError(`${sourceId}: source did not provide an as-of date`);
  }
  const sourceTime = Date.parse(`${sourceAsOf}T00:00:00Z`);
  const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  const ageDays = Math.floor((today - sourceTime) / 86_400_000);
  if (ageDays < -2) {
    throw new UniverseUpdateError(`${sourceId}: source date is unexpectedly in the future`);
  }
  if (ageDays > 14) {
    throw new UniverseUpdateError(`${sourceId}: source data is stale (${ageDays} days old)`);
  }
}

export function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;
  const source = String(text || "").replace(/^\uFEFF/u, "");
  for (let index = 0; index < source.length; index += 1) {
    const char = source[index];
    if (quoted) {
      if (char === '"' && source[index + 1] === '"') {
        field += '"';
        index += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        field += char;
      }
      continue;
    }
    if (char === '"') {
      quoted = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n") {
      row.push(field.replace(/\r$/u, ""));
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += char;
    }
  }
  if (quoted) throw new UniverseUpdateError("unterminated CSV quote");
  if (field.length || row.length) {
    row.push(field.replace(/\r$/u, ""));
    rows.push(row);
  }
  return rows;
}

function rowObject(headers, row) {
  const result = {};
  for (let index = 0; index < headers.length; index += 1) {
    result[headers[index]] = row[index] ?? "";
  }
  return result;
}

export function parseIsharesCsv(text) {
  const dateMatch = String(text || "").slice(0, 1000).match(ISHARES_DATE_PATTERN);
  const sourceAsOf = dateMatch ? isoDate(dateMatch[1]) : null;
  const rows = parseCsv(text);
  const headerIndex = rows.findIndex(
    (row) => row?.[0]?.trim() === "Ticker" && row.includes("Asset Class"),
  );
  if (headerIndex < 0) throw new UniverseUpdateError("iShares CSV header was not found");
  const headers = rows[headerIndex].map((value) => value.trim());
  const members = [];
  for (const values of rows.slice(headerIndex + 1)) {
    const row = rowObject(headers, values);
    if (String(row["Asset Class"] || "").trim() !== "Equity") continue;
    const sourceTicker = String(row.Ticker || "").trim().toUpperCase();
    try {
      members.push({
        ticker: normalizeTicker(sourceTicker),
        sourceTicker,
        companyName: cleanText(row.Name),
        sector: cleanText(row.Sector),
        weight: optionalFloat(row["Weight (%)"]),
        marketValue: optionalFloat(row["Market Value"]),
      });
    } catch (error) {
      if (!(error instanceof UniverseUpdateError)) throw error;
    }
  }
  return { sourceAsOf, members };
}

export function parseNasdaqJson(payload) {
  if (payload?.status?.rCode != null && payload.status.rCode !== 200) {
    throw new UniverseUpdateError(`Nasdaq API returned status: ${JSON.stringify(payload.status)}`);
  }
  const container = payload?.data;
  const rows = container?.data?.rows;
  if (!Array.isArray(rows)) throw new UniverseUpdateError("Nasdaq JSON rows were not found");
  const sourceAsOf = isoDate(container?.date);
  const members = [];
  for (const row of rows) {
    if (!row || typeof row !== "object") continue;
    const sourceTicker = String(row.symbol || "").trim().toUpperCase();
    try {
      members.push({
        ticker: normalizeTicker(sourceTicker),
        sourceTicker,
        companyName: cleanText(row.companyName),
        sector: cleanText(row.sector),
        weight: null,
        marketValue: optionalFloat(row.marketCap),
      });
    } catch (error) {
      if (!(error instanceof UniverseUpdateError)) throw error;
    }
  }
  return { sourceAsOf, members };
}

export function parseNasdaqGiwJson(payload, sourceAsOf) {
  const rows = payload?.aaData;
  if (!Array.isArray(rows)) throw new UniverseUpdateError("Nasdaq GIW JSON rows were not found");
  if (payload.iTotalRecords != null && Number(payload.iTotalRecords) !== rows.length) {
    throw new UniverseUpdateError("Nasdaq GIW reported count does not match returned rows");
  }
  const members = [];
  for (const row of rows) {
    if (!row || typeof row !== "object") continue;
    const sourceTicker = String(row.Symbol || "").trim().toUpperCase();
    try {
      members.push({
        ticker: normalizeTicker(sourceTicker),
        sourceTicker,
        companyName: cleanText(row.Name),
        sector: null,
        weight: null,
        marketValue: null,
      });
    } catch (error) {
      if (!(error instanceof UniverseUpdateError)) throw error;
    }
  }
  return { sourceAsOf, members };
}

export function parseInvescoJson(payload) {
  const rows = payload?.holdings;
  if (!Array.isArray(rows)) throw new UniverseUpdateError("Invesco JSON holdings were not found");
  const sourceAsOf = isoDate(
    cleanText(payload.effectiveBusinessDate) || cleanText(payload.effectiveDate),
  );
  const allowedTypes = new Set(["ADR", "COM", "DRNY"]);
  const members = [];
  for (const row of rows) {
    if (!row || typeof row !== "object") continue;
    if (!allowedTypes.has(String(row.securityTypeCode || "").trim().toUpperCase())) continue;
    const sourceTicker = String(row.ticker || "").trim().toUpperCase();
    try {
      members.push({
        ticker: normalizeTicker(sourceTicker),
        sourceTicker,
        companyName: cleanText(row.issuerName),
        sector: null,
        weight: optionalFloat(row.percentageOfTotalNetAssets),
        marketValue: optionalFloat(row.marketValueBase),
      });
    } catch (error) {
      if (!(error instanceof UniverseUpdateError)) throw error;
    }
  }
  return { sourceAsOf, members };
}

function recentWeekdays(start, limit) {
  const dates = [];
  const cursor = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth(), start.getUTCDate()));
  while (dates.length < limit) {
    const weekday = cursor.getUTCDay();
    if (weekday !== 0 && weekday !== 6) dates.push(cursor.toISOString().slice(0, 10));
    cursor.setUTCDate(cursor.getUTCDate() - 1);
  }
  return dates;
}

function sleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function fetchWithRetry(url, options = {}, attempts = 4) {
  let lastError;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort("timeout"), 30_000);
    try {
      const response = await fetch(url, {
        ...options,
        redirect: "follow",
        signal: controller.signal,
        headers: {
          Accept: "application/json,text/csv,text/plain;q=0.9,*/*;q=0.8",
          "User-Agent":
            "Mozilla/5.0 (compatible; BacktestStockUniverseUpdater/1.0; +https://github.com/chihung1024/backteststock)",
          ...(options.headers || {}),
        },
      });
      if (response.ok) return response;
      lastError = new UniverseUpdateError(`source HTTP ${response.status}`);
      if (!RETRYABLE_STATUS.has(response.status)) throw lastError;
    } catch (error) {
      lastError = error;
      if (attempt === attempts - 1) throw error;
    } finally {
      clearTimeout(timeout);
    }
    if (attempt < attempts - 1) await sleep([250, 800, 1600][attempt] || 1600);
  }
  throw lastError || new UniverseUpdateError("source request failed");
}

async function fetchNasdaqGiw(endpoint) {
  for (const tradeDate of recentWeekdays(new Date(), NASDAQ_GIW_LOOKBACK_WEEKDAYS)) {
    const body = new URLSearchParams({
      id: "NDX",
      tradeDate: `${tradeDate}T00:00:00.000`,
      timeOfDay: "SOD",
    });
    const response = await fetchWithRetry(endpoint.fetchUrl || endpoint.sourceUrl, {
      method: "POST",
      body,
      headers: {
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        Referer: NASDAQ_GIW_SOURCE_URL,
        "X-Requested-With": "XMLHttpRequest",
      },
    });
    const payload = await response.json();
    if (Array.isArray(payload?.aaData) && payload.aaData.length) {
      return parseNasdaqGiwJson(payload, tradeDate);
    }
    if (!Array.isArray(payload?.aaData)) {
      throw new UniverseUpdateError("Nasdaq GIW returned an invalid payload");
    }
  }
  throw new UniverseUpdateError(
    `Nasdaq GIW returned no rows for the last ${NASDAQ_GIW_LOOKBACK_WEEKDAYS} weekdays`,
  );
}

export function deduplicateMembers(members) {
  const byTicker = new Map();
  for (const member of members || []) {
    if (!byTicker.has(member.ticker)) byTicker.set(member.ticker, member);
  }
  return [...byTicker.values()].sort((left, right) => left.ticker.localeCompare(right.ticker));
}

async function checksumMembers(members) {
  const content = members.map((member) => member.ticker).join("\n");
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(content));
  return [...new Uint8Array(digest)]
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}

export function validateSnapshot(source, members, previousMembers = null) {
  const memberCount = members.length;
  if (memberCount < source.minMembers || memberCount > source.maxMembers) {
    throw new UniverseUpdateError(
      `${source.id}: member count ${memberCount} is outside ${source.minMembers}..${source.maxMembers}`,
    );
  }
  if (new Set(members.map((member) => member.ticker)).size !== memberCount) {
    throw new UniverseUpdateError(`${source.id}: duplicate normalized tickers remain`);
  }
  if (previousMembers?.size) {
    const previousCount = previousMembers.size;
    const countChange = Math.abs(memberCount - previousCount) / previousCount;
    if (countChange > source.maxCountChangeRatio) {
      throw new UniverseUpdateError(
        `${source.id}: member count changed ${(countChange * 100).toFixed(1)}%; limit is ${(source.maxCountChangeRatio * 100).toFixed(1)}%`,
      );
    }
    const current = new Set(members.map((member) => member.ticker));
    let retained = 0;
    for (const ticker of previousMembers) if (current.has(ticker)) retained += 1;
    const churn = 1 - retained / previousCount;
    if (churn > source.maxMembershipChurnRatio) {
      throw new UniverseUpdateError(
        `${source.id}: membership churn is ${(churn * 100).toFixed(1)}%; limit is ${(source.maxMembershipChurnRatio * 100).toFixed(1)}%`,
      );
    }
  }
}

async function currentMembers(db, universeId) {
  const row = await db.prepare(
    `SELECT
       v.member_count,
       (
         SELECT json_group_array(ticker)
         FROM (
           SELECT m.ticker AS ticker
           FROM universe_members AS m
           WHERE m.version_id = v.id
           ORDER BY m.ticker
         )
       ) AS members_json
     FROM universe_current AS c
     JOIN universe_versions AS v ON v.id = c.version_id
     WHERE c.universe_id = ?1`,
  ).bind(universeId).first();
  if (!row) return null;
  let tickers;
  try {
    tickers = JSON.parse(row.members_json || "[]");
  } catch {
    throw new UniverseUpdateError(`${universeId}: current member JSON is invalid`);
  }
  if (!Array.isArray(tickers) || tickers.length !== Number(row.member_count)) {
    throw new UniverseUpdateError(`${universeId}: current member count is inconsistent`);
  }
  return new Set(tickers.map((ticker) => String(ticker)));
}

async function fetchSnapshot(source, previousMembers) {
  const endpoints = [endpointFrom(source), ...(source.fallbacks || [])];
  const failures = [];
  for (const endpoint of endpoints) {
    try {
      let parsed;
      if (endpoint.adapter === "nasdaq_giw_json") {
        parsed = await fetchNasdaqGiw(endpoint);
      } else {
        const response = await fetchWithRetry(endpoint.fetchUrl || endpoint.sourceUrl);
        if (endpoint.adapter === "ishares_csv") {
          parsed = parseIsharesCsv(await response.text());
        } else if (endpoint.adapter === "nasdaq_json") {
          parsed = parseNasdaqJson(await response.json());
        } else if (endpoint.adapter === "invesco_json") {
          parsed = parseInvescoJson(await response.json());
        } else {
          throw new UniverseUpdateError(`unsupported adapter: ${endpoint.adapter}`);
        }
      }
      validateSourceDate(source.id, parsed.sourceAsOf);
      const members = deduplicateMembers(parsed.members);
      validateSnapshot(source, members, previousMembers);
      const checksum = await checksumMembers(members);
      const fetchedAt = nowIso();
      return {
        source,
        effectiveSource: endpoint,
        sourceAsOf: parsed.sourceAsOf,
        fetchedAt,
        checksum,
        version: `${parsed.sourceAsOf}-${checksum.slice(0, 12)}`,
        members,
      };
    } catch (error) {
      failures.push(`${endpoint.sourceLabel}: ${String(error?.message || error)}`);
    }
  }
  throw new UniverseUpdateError(
    `${source.id}: all configured sources failed (${failures.join("; ")})`,
  );
}

async function existingVersion(db, snapshot) {
  return db.prepare(
    `SELECT
       v.id, v.checksum, v.member_count,
       CASE WHEN c.version_id = v.id THEN 1 ELSE 0 END AS is_current,
       (SELECT COUNT(*) FROM universe_members AS m WHERE m.version_id = v.id) AS stored_count
     FROM universe_versions AS v
     LEFT JOIN universe_current AS c ON c.universe_id = v.universe_id
     WHERE v.universe_id = ?1 AND v.version = ?2
     LIMIT 1`,
  ).bind(snapshot.source.id, snapshot.version).first();
}

async function publishSnapshot(db, snapshot) {
  const source = snapshot.source;
  const effective = snapshot.effectiveSource;
  const existing = await existingVersion(db, snapshot);
  const versionId = existing?.id || crypto.randomUUID();
  const canReuseMembers = Boolean(
    existing
      && existing.checksum === snapshot.checksum
      && Number(existing.member_count) === snapshot.members.length
      && Number(existing.stored_count) === snapshot.members.length,
  );
  if (existing?.is_current && !canReuseMembers) {
    throw new UniverseUpdateError(`${source.id}: refusing to rebuild the currently active version`);
  }

  await db.prepare(
    `INSERT INTO universe_versions (
       id, universe_id, version, source_as_of, fetched_at, source_label,
       source_url, is_proxy, checksum, member_count, status, warning
     ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, 'staging', ?11)
     ON CONFLICT(universe_id, version) DO UPDATE SET
       source_as_of = excluded.source_as_of,
       fetched_at = excluded.fetched_at,
       source_label = excluded.source_label,
       source_url = excluded.source_url,
       is_proxy = excluded.is_proxy,
       checksum = excluded.checksum,
       member_count = excluded.member_count,
       status = 'staging',
       warning = excluded.warning`,
  ).bind(
    versionId,
    source.id,
    snapshot.version,
    snapshot.sourceAsOf,
    snapshot.fetchedAt,
    effective.sourceLabel,
    effective.sourceUrl,
    effective.isProxy ? 1 : 0,
    snapshot.checksum,
    snapshot.members.length,
    effective.proxyNote || null,
  ).run();

  if (!canReuseMembers) {
    await db.prepare("DELETE FROM universe_members WHERE version_id = ?1")
      .bind(versionId)
      .run();
    await db.prepare(
      `INSERT OR REPLACE INTO universe_members (
         version_id, ticker, source_ticker, company_name, sector, weight, market_value
       )
       SELECT
         ?1,
         json_extract(value, '$.ticker'),
         json_extract(value, '$.sourceTicker'),
         json_extract(value, '$.companyName'),
         json_extract(value, '$.sector'),
         json_extract(value, '$.weight'),
         json_extract(value, '$.marketValue')
       FROM json_each(?2)`,
    ).bind(versionId, JSON.stringify(snapshot.members)).run();
  }

  const storedCount = await db.prepare(
    "SELECT COUNT(*) AS member_count FROM universe_members WHERE version_id = ?1",
  ).bind(versionId).first("member_count");
  if (Number(storedCount) !== snapshot.members.length) {
    throw new UniverseUpdateError(
      `${source.id}: D1 verification expected ${snapshot.members.length}, got ${storedCount}`,
    );
  }

  await db.batch([
    db.prepare("UPDATE universe_versions SET status = 'active' WHERE id = ?1")
      .bind(versionId),
    db.prepare(
      `INSERT INTO universe_current (universe_id, version_id, promoted_at)
       VALUES (?1, ?2, ?3)
       ON CONFLICT(universe_id) DO UPDATE SET
         version_id = excluded.version_id,
         promoted_at = excluded.promoted_at`,
    ).bind(source.id, versionId, nowIso()),
    db.prepare(
      `UPDATE universe_versions
       SET status = 'archived'
       WHERE universe_id = ?1 AND id != ?2 AND status = 'active'`,
    ).bind(source.id, versionId),
    db.prepare(
      `DELETE FROM universe_versions
       WHERE universe_id = ?1
         AND id != ?2
         AND id NOT IN (
           SELECT id FROM universe_versions
           WHERE universe_id = ?1
           ORDER BY fetched_at DESC
           LIMIT ?3
         )`,
    ).bind(source.id, versionId, MAX_RETAINED_VERSIONS),
  ]);
  return versionId;
}

export async function updateUniverses(env, trigger = {}) {
  if (!env?.DB) throw new UniverseUpdateError("Universe D1 binding is unavailable");
  const sources = sourceDefinitions(env);
  const report = {
    startedAt: nowIso(),
    trigger: {
      cron: trigger.cron || null,
      scheduledTime: trigger.scheduledTime || null,
    },
    universes: [],
    errors: [],
  };
  for (const source of sources) {
    try {
      const previous = await currentMembers(env.DB, source.id);
      const snapshot = await fetchSnapshot(source, previous);
      const versionId = await publishSnapshot(env.DB, snapshot);
      report.universes.push({
        id: source.id,
        source: snapshot.effectiveSource.sourceLabel,
        sourceUrl: snapshot.effectiveSource.sourceUrl,
        sourceAsOf: snapshot.sourceAsOf,
        fetchedAt: snapshot.fetchedAt,
        version: snapshot.version,
        checksum: snapshot.checksum,
        memberCount: snapshot.members.length,
        versionId,
        isProxy: Boolean(snapshot.effectiveSource.isProxy),
        fallbackUsed: snapshot.effectiveSource.sourceUrl !== source.sourceUrl,
      });
      console.log("Universe cron published", report.universes.at(-1));
    } catch (error) {
      const message = String(error?.message || error);
      report.errors.push({ id: source.id, error: message });
      console.error("Universe cron source failed", { id: source.id, error: message });
    }
  }
  report.finishedAt = nowIso();
  report.ok = report.errors.length === 0 && report.universes.length === sources.length;
  if (!report.ok) {
    throw new UniverseUpdateError(`Universe scheduled update incomplete: ${JSON.stringify(report.errors)}`);
  }
  return report;
}
