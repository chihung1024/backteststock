UPDATE universes
SET
  description = '優先使用 Nasdaq 官方公開 API；不可用時使用 Nasdaq Global Index Watch 官方成分資料，再以 Invesco QQQM 公開持股作最後備援。',
  source_label = 'Nasdaq official API / Global Index Watch / Invesco QQQM fallback',
  updated_at = CURRENT_TIMESTAMP
WHERE id = 'nasdaq100';
