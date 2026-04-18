PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_key TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  root_path TEXT,
  default_branch TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL,
  runtime TEXT NOT NULL,
  external_session_id TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  cwd TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  UNIQUE(project_id, runtime, external_session_id),
  FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS turns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL,
  external_turn_id TEXT NOT NULL,
  captured_at TEXT NOT NULL,
  input_messages_json TEXT NOT NULL,
  assistant_message TEXT NOT NULL,
  tool_events_json TEXT NOT NULL DEFAULT '[]',
  raw_payload_json TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  UNIQUE(session_id, external_turn_id),
  FOREIGN KEY(session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS observations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL,
  session_id INTEGER,
  turn_id INTEGER,
  type TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT '',
  confidence REAL NOT NULL DEFAULT 0.5,
  importance INTEGER NOT NULL DEFAULT 2,
  status TEXT NOT NULL DEFAULT 'snapshot',
  source_runtime TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  dedupe_hash TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id),
  FOREIGN KEY(session_id) REFERENCES sessions(id),
  FOREIGN KEY(turn_id) REFERENCES turns(id)
);

CREATE TABLE IF NOT EXISTS observation_files (
  observation_id INTEGER NOT NULL,
  file_path TEXT NOT NULL,
  PRIMARY KEY(observation_id, file_path),
  FOREIGN KEY(observation_id) REFERENCES observations(id)
);

CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL,
  source_observation_id INTEGER NOT NULL UNIQUE,
  title TEXT NOT NULL,
  decision_text TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id),
  FOREIGN KEY(source_observation_id) REFERENCES observations(id)
);

CREATE TABLE IF NOT EXISTS context_sync_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL,
  target_path TEXT,
  skipped INTEGER NOT NULL DEFAULT 0,
  reason TEXT,
  source_char_count INTEGER NOT NULL,
  pack_char_count INTEGER NOT NULL,
  approx_source_tokens INTEGER NOT NULL,
  approx_pack_tokens INTEGER NOT NULL,
  compression_ratio REAL NOT NULL,
  budget TEXT NOT NULL DEFAULT 'normal',
  budget_reason TEXT,
  build_ms REAL NOT NULL DEFAULT 0,
  generated_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS closure_check_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL,
  turn_id INTEGER,
  event_kind TEXT NOT NULL,
  passed INTEGER NOT NULL DEFAULT 0,
  reasons_json TEXT NOT NULL DEFAULT '[]',
  pending_count INTEGER NOT NULL DEFAULT 0,
  blocker_count INTEGER NOT NULL DEFAULT 0,
  dod_missing_count INTEGER NOT NULL DEFAULT 0,
  evidence_count INTEGER NOT NULL DEFAULT 0,
  completion_claim_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id),
  FOREIGN KEY(turn_id) REFERENCES turns(id)
);

CREATE TABLE IF NOT EXISTS memory_provenance (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  memory_kind TEXT NOT NULL,
  memory_id INTEGER NOT NULL,
  project_id INTEGER NOT NULL,
  session_id INTEGER,
  turn_id INTEGER,
  observation_id INTEGER,
  turn_hash TEXT,
  model_name TEXT,
  cwd TEXT,
  source_span_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  UNIQUE(memory_kind, memory_id),
  FOREIGN KEY(project_id) REFERENCES projects(id),
  FOREIGN KEY(session_id) REFERENCES sessions(id),
  FOREIGN KEY(turn_id) REFERENCES turns(id),
  FOREIGN KEY(observation_id) REFERENCES observations(id)
);

CREATE TABLE IF NOT EXISTS memory_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL,
  label TEXT NOT NULL,
  snapshot_hash TEXT NOT NULL,
  snapshot_path TEXT NOT NULL,
  created_from_sync_event_id INTEGER,
  restored_at TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id),
  FOREIGN KEY(created_from_sync_event_id) REFERENCES context_sync_events(id)
);

CREATE TABLE IF NOT EXISTS health_reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL,
  score INTEGER NOT NULL,
  duplicate_count INTEGER NOT NULL DEFAULT 0,
  contradiction_count INTEGER NOT NULL DEFAULT 0,
  stale_item_count INTEGER NOT NULL DEFAULT 0,
  dod_total_count INTEGER NOT NULL DEFAULT 0,
  dod_missing_count INTEGER NOT NULL DEFAULT 0,
  dod_coverage_ratio REAL NOT NULL DEFAULT 1.0,
  open_work_count INTEGER NOT NULL DEFAULT 0,
  closure_mismatch INTEGER NOT NULL DEFAULT 0,
  details_json TEXT NOT NULL DEFAULT '{}',
  generated_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS memory_policies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL,
  policy_kind TEXT NOT NULL,
  rule_json TEXT NOT NULL DEFAULT '{}',
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS project_inheritances (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  target_project_id INTEGER NOT NULL,
  source_project_id INTEGER NOT NULL,
  mode TEXT NOT NULL,
  selector_json TEXT NOT NULL DEFAULT '{}',
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  FOREIGN KEY(target_project_id) REFERENCES projects(id),
  FOREIGN KEY(source_project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS repair_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL,
  health_report_id INTEGER,
  repair_kind TEXT NOT NULL,
  before_ref_json TEXT NOT NULL DEFAULT '{}',
  after_ref_json TEXT NOT NULL DEFAULT '{}',
  approved INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id),
  FOREIGN KEY(health_report_id) REFERENCES health_reports(id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS observations_fts USING fts5(
  title,
  summary,
  detail,
  content='observations',
  content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS observations_ai AFTER INSERT ON observations BEGIN
  INSERT INTO observations_fts(rowid, title, summary, detail)
  VALUES (new.id, new.title, new.summary, new.detail);
END;

CREATE TRIGGER IF NOT EXISTS observations_ad AFTER DELETE ON observations BEGIN
  INSERT INTO observations_fts(observations_fts, rowid, title, summary, detail)
  VALUES('delete', old.id, old.title, old.summary, old.detail);
END;

CREATE TRIGGER IF NOT EXISTS observations_au AFTER UPDATE ON observations BEGIN
  INSERT INTO observations_fts(observations_fts, rowid, title, summary, detail)
  VALUES('delete', old.id, old.title, old.summary, old.detail);
  INSERT INTO observations_fts(rowid, title, summary, detail)
  VALUES (new.id, new.title, new.summary, new.detail);
END;

CREATE INDEX IF NOT EXISTS idx_sessions_project_id ON sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_turns_session_id ON turns(session_id);
CREATE INDEX IF NOT EXISTS idx_observations_project_id ON observations(project_id);
CREATE INDEX IF NOT EXISTS idx_observations_updated_at ON observations(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_decisions_project_id ON decisions(project_id);
CREATE INDEX IF NOT EXISTS idx_context_sync_events_project_id ON context_sync_events(project_id);
CREATE INDEX IF NOT EXISTS idx_context_sync_events_generated_at ON context_sync_events(generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_closure_check_events_project_id ON closure_check_events(project_id);
CREATE INDEX IF NOT EXISTS idx_closure_check_events_created_at ON closure_check_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_provenance_project_id ON memory_provenance(project_id);
CREATE INDEX IF NOT EXISTS idx_memory_provenance_turn_id ON memory_provenance(turn_id);
CREATE INDEX IF NOT EXISTS idx_memory_provenance_observation_id ON memory_provenance(observation_id);
CREATE INDEX IF NOT EXISTS idx_memory_snapshots_project_id ON memory_snapshots(project_id);
CREATE INDEX IF NOT EXISTS idx_memory_snapshots_created_at ON memory_snapshots(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_health_reports_project_id ON health_reports(project_id);
CREATE INDEX IF NOT EXISTS idx_health_reports_generated_at ON health_reports(generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_policies_project_id ON memory_policies(project_id);
CREATE INDEX IF NOT EXISTS idx_project_inheritances_target_project_id ON project_inheritances(target_project_id);
CREATE INDEX IF NOT EXISTS idx_project_inheritances_source_project_id ON project_inheritances(source_project_id);
CREATE INDEX IF NOT EXISTS idx_repair_events_project_id ON repair_events(project_id);
CREATE INDEX IF NOT EXISTS idx_repair_events_created_at ON repair_events(created_at DESC);
