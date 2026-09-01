-- Cross-table references (fills.strategy_id → strategies, experiments.hypothesis_id → hypotheses,
-- etc.) are enforced at the application layer rather than via FK constraints. This is intentional:
-- many writes are append-only audit records that must survive even if a referenced row is absent
-- (e.g., audit_events and fills may be written after a strategy is deleted or during bootstrap
-- before the strategies row exists). Application-layer enforcement is implemented in
-- StrategyRegistry.upsert(), OrderManager.register_intent(), and MemoryStore.record_fill().
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS audit_events(
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  event_type TEXT NOT NULL,
  instance_id TEXT NOT NULL,
  payload JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_events_ts_idx ON audit_events(ts DESC);

CREATE TABLE IF NOT EXISTS memories(
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  memory_type TEXT NOT NULL,
  subject TEXT NOT NULL,
  summary TEXT NOT NULL,
  evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
  confidence DOUBLE PRECISION NOT NULL DEFAULT .5,
  expires_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS memories_subject_idx ON memories(subject,ts DESC);

CREATE TABLE IF NOT EXISTS strategies(
  strategy_id TEXT PRIMARY KEY,
  version INTEGER NOT NULL DEFAULT 1,
  state TEXT NOT NULL,
  spec JSONB NOT NULL,
  metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS hypotheses(
  hypothesis_id TEXT PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  subject TEXT NOT NULL,
  statement TEXT NOT NULL,
  counter_hypothesis TEXT NOT NULL,
  priority DOUBLE PRECISION NOT NULL,
  status TEXT NOT NULL DEFAULT 'OPEN',
  evidence JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS experiments(
  experiment_id TEXT PRIMARY KEY,
  hypothesis_id TEXT,
  strategy_id TEXT,
  dataset_hash TEXT NOT NULL,
  parameters JSONB NOT NULL,
  results JSONB,
  status TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS decisions(
  decision_id TEXT PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  world_version BIGINT NOT NULL,
  instrument TEXT,
  context JSONB NOT NULL,
  decision JSONB NOT NULL,
  outcome JSONB
);

CREATE TABLE IF NOT EXISTS fills(
  fill_id TEXT PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  venue TEXT,
  instrument TEXT,
  strategy_id TEXT,
  qty DOUBLE PRECISION,
  price DOUBLE PRECISION,
  fees DOUBLE PRECISION DEFAULT 0,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS connector_health(
  connector TEXT PRIMARY KEY,
  state TEXT NOT NULL,
  last_event_ts TIMESTAMPTZ,
  last_ok_ts TIMESTAMPTZ,
  details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS latest_market_state(
  instrument TEXT PRIMARY KEY,
  venue TEXT NOT NULL,
  asset_class TEXT NOT NULL,
  ts TIMESTAMPTZ NOT NULL,
  price DOUBLE PRECISION NOT NULL,
  bid DOUBLE PRECISION,
  ask DOUBLE PRECISION,
  volume DOUBLE PRECISION,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS latest_market_state_ts_idx ON latest_market_state(ts DESC);

CREATE TABLE IF NOT EXISTS market_bars(
  instrument TEXT NOT NULL,
  venue TEXT NOT NULL,
  asset_class TEXT NOT NULL,
  interval_seconds INTEGER NOT NULL,
  ts TIMESTAMPTZ NOT NULL,
  open DOUBLE PRECISION NOT NULL,
  high DOUBLE PRECISION NOT NULL,
  low DOUBLE PRECISION NOT NULL,
  close DOUBLE PRECISION NOT NULL,
  volume DOUBLE PRECISION NOT NULL DEFAULT 0,
  PRIMARY KEY(instrument,interval_seconds,ts)
);
CREATE INDEX IF NOT EXISTS market_bars_lookup_idx ON market_bars(instrument,interval_seconds,ts DESC);

CREATE TABLE IF NOT EXISTS strategy_positions(
  strategy_id TEXT NOT NULL,
  venue TEXT NOT NULL,
  instrument TEXT NOT NULL,
  qty DOUBLE PRECISION NOT NULL DEFAULT 0,
  avg_price DOUBLE PRECISION NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(strategy_id,venue,instrument)
);

CREATE TABLE IF NOT EXISTS strategy_performance(
  id BIGSERIAL PRIMARY KEY,
  strategy_id TEXT NOT NULL,
  stage TEXT NOT NULL,
  ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  pnl DOUBLE PRECISION NOT NULL DEFAULT 0,
  equity DOUBLE PRECISION,
  drawdown DOUBLE PRECISION,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS strategy_performance_idx ON strategy_performance(strategy_id,ts DESC);

CREATE TABLE IF NOT EXISTS orders(
  order_id TEXT PRIMARY KEY,
  client_order_id TEXT UNIQUE NOT NULL,
  decision_id TEXT,
  strategy_id TEXT NOT NULL,
  venue TEXT NOT NULL,
  instrument TEXT NOT NULL,
  side TEXT NOT NULL,
  requested_qty DOUBLE PRECISION NOT NULL,
  approved_qty DOUBLE PRECISION,
  status TEXT NOT NULL,
  response JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS orders_pending_idx ON orders(strategy_id,venue,instrument,status);

ALTER TABLE strategy_positions ADD COLUMN IF NOT EXISTS risk_dollars DOUBLE PRECISION NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS account_equity_snapshots(
  venue TEXT NOT NULL,
  ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  equity DOUBLE PRECISION NOT NULL,
  cash DOUBLE PRECISION NOT NULL,
  PRIMARY KEY(venue,ts)
);
CREATE INDEX IF NOT EXISTS equity_snapshot_lookup_idx ON account_equity_snapshots(venue,ts DESC);
ALTER TABLE strategy_positions ADD COLUMN IF NOT EXISTS realized_pnl DOUBLE PRECISION NOT NULL DEFAULT 0;
ALTER TABLE strategy_positions ADD COLUMN IF NOT EXISTS capital_base DOUBLE PRECISION NOT NULL DEFAULT 0;
