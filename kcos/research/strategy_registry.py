from __future__ import annotations

import json

import psycopg
from psycopg.rows import dict_row

from ..domain import StrategyRecord
from ..memory import _connect


class StrategyRegistry:
    def __init__(self, dsn: str):
        self.dsn = dsn

    def upsert(self, strategy: StrategyRecord) -> None:
        sql = """
        INSERT INTO strategies(strategy_id,version,state,spec,metrics,updated_at)
        VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,now())
        ON CONFLICT(strategy_id) DO UPDATE SET
          version=excluded.version,state=excluded.state,spec=excluded.spec,metrics=excluded.metrics,updated_at=now()
        """
        with _connect(self.dsn) as conn:
            conn.execute(sql, (strategy.strategy_id, strategy.version, strategy.stage, json.dumps(strategy.spec, default=str), json.dumps(strategy.metrics, default=str)))

    @staticmethod
    def _row(row) -> StrategyRecord:
        spec = row["spec"] or {}
        metrics = row["metrics"] or {}
        return StrategyRecord(
            row["strategy_id"], int(row["version"]), row["state"],
            spec.get("asset_class", "UNKNOWN"), spec.get("universe", []), spec.get("hypothesis_id"),
            spec, metrics, float(metrics.get("allocation", 0.0) or 0.0), bool(metrics.get("enabled", True)),
        )

    # Active stages that participate in the heartbeat decision loop.
    ACTIVE_STAGES: frozenset[str] = frozenset({"RESEARCH", "WALK_FORWARD", "PAPER", "CANARY", "LIVE", "SCALED"})

    def list(self, stages: set[str] | None = None) -> list[StrategyRecord]:
        # Default to active stages only to avoid unbounded full-table scans on every
        # 6-second heartbeat. Pass stages=None explicitly only when a full scan is
        # genuinely required (e.g., admin reporting).
        effective_stages = stages if stages is not None else self.ACTIVE_STAGES
        sql = "SELECT strategy_id,version,state,spec,metrics FROM strategies"
        args: tuple = ()
        if effective_stages:
            sql += " WHERE state=ANY(%s)"
            args = (list(effective_stages),)
        sql += " ORDER BY updated_at DESC"
        with _connect(self.dsn, row_factory=dict_row) as conn:
            rows = conn.execute(sql, args).fetchall()
        return [self._row(r) for r in rows]

    def get(self, strategy_id: str) -> StrategyRecord | None:
        with _connect(self.dsn, row_factory=dict_row) as conn:
            row = conn.execute(
                "SELECT strategy_id,version,state,spec,metrics FROM strategies WHERE strategy_id=%s",
                (strategy_id,),
            ).fetchone()
        return self._row(row) if row else None

    def update_metrics(self, strategy_id: str, metrics: dict, stage: str | None = None) -> StrategyRecord | None:
        strategy = self.get(strategy_id)
        if not strategy:
            return None
        strategy.metrics.update(metrics)
        if stage:
            strategy.stage = stage
        strategy.version += 1
        self.upsert(strategy)
        return strategy
