CREATE TABLE IF NOT EXISTS research_libraries (
  library_id TEXT PRIMARY KEY,
  capability_hash TEXT NOT NULL UNIQUE,
  capability_hash_version TEXT NOT NULL DEFAULT 'sha256-v1',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_used_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK (length(library_id) BETWEEN 8 AND 80),
  CHECK (length(capability_hash) = 64)
);

CREATE TABLE IF NOT EXISTS research_runs (
  run_id TEXT PRIMARY KEY,
  library_id TEXT NOT NULL REFERENCES research_libraries(library_id) ON DELETE CASCADE,
  source_run_id TEXT REFERENCES research_runs(run_id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  job_hash TEXT NOT NULL,
  execution_request_json TEXT NOT NULL,
  result_json TEXT NOT NULL,
  result_contract_version TEXT NOT NULL,
  decision_count INTEGER NOT NULL CHECK (decision_count >= 1),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK (length(run_id) BETWEEN 8 AND 80),
  CHECK (length(name) BETWEEN 1 AND 120),
  CHECK (length(job_hash) = 64)
);

CREATE INDEX IF NOT EXISTS idx_research_runs_library_created
  ON research_runs(library_id, created_at DESC, run_id DESC);

CREATE INDEX IF NOT EXISTS idx_research_runs_library_job
  ON research_runs(library_id, job_hash, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_research_runs_source
  ON research_runs(source_run_id)
  WHERE source_run_id IS NOT NULL;
