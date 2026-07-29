UPDATE universes
SET
  description = '使用 Nasdaq Global Index Watch 官方 NDX 成分資料；不可用時再以 Nasdaq 公開 API 與 Invesco QQQM 公開持股依序備援。',
  source_label = 'Nasdaq Global Index Watch / Nasdaq API / Invesco QQQM fallback',
  source_url = 'https://indexes.nasdaq.com/Index/Weighting/NDX',
  updated_at = CURRENT_TIMESTAMP
WHERE id = 'nasdaq100';
