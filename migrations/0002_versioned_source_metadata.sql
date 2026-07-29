ALTER TABLE universe_versions
  ADD COLUMN source_label TEXT NOT NULL DEFAULT '';

ALTER TABLE universe_versions
  ADD COLUMN is_proxy INTEGER NOT NULL DEFAULT 0 CHECK (is_proxy IN (0, 1));

UPDATE universe_versions
SET
  source_label = COALESCE(
    (SELECT source_label FROM universes WHERE universes.id = universe_versions.universe_id),
    ''
  ),
  is_proxy = COALESCE(
    (SELECT is_proxy FROM universes WHERE universes.id = universe_versions.universe_id),
    0
  );

UPDATE universes
SET
  name = 'NASDAQ-100（自動備援）',
  description = '優先使用 Nasdaq 官方公開 API；不可用時使用追蹤 Nasdaq-100 的 Invesco QQQM 每日公開股票持股。',
  source_label = 'Nasdaq official API / Invesco QQQM fallback',
  source_url = 'https://api.nasdaq.com/api/quote/list-type/nasdaq100',
  is_proxy = 0,
  proxy_note = NULL,
  updated_at = CURRENT_TIMESTAMP
WHERE id = 'nasdaq100';
