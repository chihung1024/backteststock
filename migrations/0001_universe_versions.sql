PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS universes (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  source_label TEXT NOT NULL,
  source_url TEXT NOT NULL,
  is_proxy INTEGER NOT NULL DEFAULT 0 CHECK (is_proxy IN (0, 1)),
  proxy_note TEXT,
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  sort_order INTEGER NOT NULL DEFAULT 100,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS universe_versions (
  id TEXT PRIMARY KEY,
  universe_id TEXT NOT NULL REFERENCES universes(id) ON DELETE CASCADE,
  version TEXT NOT NULL,
  source_as_of TEXT,
  fetched_at TEXT NOT NULL,
  source_url TEXT NOT NULL,
  checksum TEXT NOT NULL,
  member_count INTEGER NOT NULL CHECK (member_count > 0),
  status TEXT NOT NULL DEFAULT 'staging' CHECK (status IN ('staging', 'active', 'archived')),
  warning TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (universe_id, version)
);

CREATE TABLE IF NOT EXISTS universe_members (
  version_id TEXT NOT NULL REFERENCES universe_versions(id) ON DELETE CASCADE,
  ticker TEXT NOT NULL,
  source_ticker TEXT NOT NULL,
  company_name TEXT,
  sector TEXT,
  weight REAL,
  market_value REAL,
  PRIMARY KEY (version_id, ticker)
);

CREATE TABLE IF NOT EXISTS universe_current (
  universe_id TEXT PRIMARY KEY REFERENCES universes(id) ON DELETE CASCADE,
  version_id TEXT NOT NULL UNIQUE REFERENCES universe_versions(id) ON DELETE RESTRICT,
  promoted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_universe_versions_universe_fetched
  ON universe_versions(universe_id, fetched_at DESC);

CREATE INDEX IF NOT EXISTS idx_universe_members_ticker
  ON universe_members(ticker);

INSERT INTO universes (
  id, name, description, source_label, source_url, is_proxy, proxy_note, sort_order
) VALUES
  (
    'sp500',
    'S&P 500（IVV holdings）',
    '以追蹤 S&P 500 的 IVV 每日公開持股作為可更新研究池。',
    'iShares IVV holdings',
    'https://www.ishares.com/us/products/239726/ishares-core-s-p-500-etf/latest-holdings.csv',
    1,
    '此清單是 IVV 公開持股代理池，可能包含現金、衍生品差異或與正式 S&P 500 授權名單存在短暫時差。',
    10
  ),
  (
    'nasdaq100',
    'NASDAQ-100',
    'Nasdaq 官方公開 API 所列 Nasdaq-100 證券。',
    'Nasdaq official API',
    'https://api.nasdaq.com/api/quote/list-type/nasdaq100',
    0,
    NULL,
    20
  ),
  (
    'soxx',
    'SOXX holdings',
    'iShares Semiconductor ETF 每日公開股票持股。',
    'iShares SOXX holdings',
    'https://www.ishares.com/us/products/239705/ishares-semiconductor-etf/latest-holdings.csv',
    0,
    NULL,
    30
  ),
  (
    'russell2000',
    'Russell 2000（IWM holdings 代理）',
    '以追蹤 Russell 2000 的 IWM 每日公開持股作為可更新研究池。',
    'iShares IWM holdings',
    'https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/latest-holdings.csv',
    1,
    '此清單是 IWM 公開持股代理池，不是 FTSE Russell 授權的正式指數成分名單，可能有追蹤誤差與調整時差。',
    40
  )
ON CONFLICT(id) DO UPDATE SET
  name = excluded.name,
  description = excluded.description,
  source_label = excluded.source_label,
  source_url = excluded.source_url,
  is_proxy = excluded.is_proxy,
  proxy_note = excluded.proxy_note,
  sort_order = excluded.sort_order,
  updated_at = CURRENT_TIMESTAMP;
