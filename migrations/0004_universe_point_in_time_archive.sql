CREATE TABLE IF NOT EXISTS universe_snapshot_archive (
  universe_id TEXT NOT NULL REFERENCES universes(id) ON DELETE CASCADE,
  source_as_of TEXT NOT NULL,
  version TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  source_label TEXT NOT NULL,
  source_url TEXT NOT NULL,
  is_proxy INTEGER NOT NULL DEFAULT 0 CHECK (is_proxy IN (0, 1)),
  warning TEXT,
  checksum TEXT NOT NULL,
  member_count INTEGER NOT NULL CHECK (member_count > 0),
  members_json TEXT NOT NULL,
  archive_format_version TEXT NOT NULL DEFAULT 'universe-members-json-v1',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (universe_id, source_as_of, version)
);

CREATE INDEX IF NOT EXISTS idx_universe_snapshot_archive_lookup
  ON universe_snapshot_archive(universe_id, source_as_of DESC, fetched_at DESC);

-- Seed only retained snapshots with an actual source observation date. This
-- preserves existing evidence without fabricating membership history.
INSERT OR IGNORE INTO universe_snapshot_archive (
  universe_id,
  source_as_of,
  version,
  fetched_at,
  source_label,
  source_url,
  is_proxy,
  warning,
  checksum,
  member_count,
  members_json
)
SELECT
  v.universe_id,
  v.source_as_of,
  v.version,
  v.fetched_at,
  v.source_label,
  v.source_url,
  v.is_proxy,
  v.warning,
  v.checksum,
  v.member_count,
  (
    SELECT json_group_array(ticker)
    FROM (
      SELECT ticker
      FROM universe_members
      WHERE version_id = v.id
      ORDER BY ticker
    )
  )
FROM universe_versions AS v
WHERE v.source_as_of IS NOT NULL
  AND (
    SELECT COUNT(*)
    FROM universe_members AS m
    WHERE m.version_id = v.id
  ) = v.member_count;

-- Existing publishing code writes members while a version is staging, verifies
-- the row count, and only then promotes that version to active. Archive at that
-- promotion boundary so the current-serving path and PIT evidence cannot drift.
CREATE TRIGGER IF NOT EXISTS archive_universe_snapshot_on_activation
AFTER UPDATE OF status ON universe_versions
WHEN NEW.status = 'active'
  AND NEW.source_as_of IS NOT NULL
  AND (
    SELECT COUNT(*)
    FROM universe_members
    WHERE version_id = NEW.id
  ) = NEW.member_count
BEGIN
  INSERT OR IGNORE INTO universe_snapshot_archive (
    universe_id,
    source_as_of,
    version,
    fetched_at,
    source_label,
    source_url,
    is_proxy,
    warning,
    checksum,
    member_count,
    members_json
  ) VALUES (
    NEW.universe_id,
    NEW.source_as_of,
    NEW.version,
    NEW.fetched_at,
    NEW.source_label,
    NEW.source_url,
    NEW.is_proxy,
    NEW.warning,
    NEW.checksum,
    NEW.member_count,
    (
      SELECT json_group_array(ticker)
      FROM (
        SELECT ticker
        FROM universe_members
        WHERE version_id = NEW.id
        ORDER BY ticker
      )
    )
  );
END;
