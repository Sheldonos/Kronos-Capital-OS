from __future__ import annotations

from typing import Any

import numpy as np
import psycopg
from psycopg.rows import dict_row


class StrategyPerformanceTracker:
    """Persistent strategy performance evidence derived from realized live/paper snapshots."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    def snapshot(self, strategy_id: str, stage: str, pnl: float, capital_base: float, metadata: dict[str, Any] | None = None) -> dict[str, float]:
        equity = max(float(capital_base), 1e-9) + float(pnl)
        with psycopg.connect(self.dsn) as conn:
            peak = conn.execute(
                "SELECT COALESCE(MAX(equity),%s) FROM strategy_performance WHERE strategy_id=%s",
                (equity, strategy_id),
            ).fetchone()[0]
            peak = max(float(peak or equity), equity)
            drawdown = max(0.0, (peak - equity) / max(peak, 1e-9))
            import json
            conn.execute(
                "INSERT INTO strategy_performance(strategy_id,stage,pnl,equity,drawdown,metadata) VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
                (strategy_id, stage, pnl, equity, drawdown, json.dumps(metadata or {}, default=str)),
            )
        return {"equity": equity, "drawdown": drawdown}

    @staticmethod
    def _return_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
        if len(rows) < 2:
            return {"live_sharpe": 0.0, "net_expectancy": 0.0, "decay": 0.0}
        equities = np.asarray([max(float(x["equity"]), 1e-9) for x in rows], dtype=float)
        returns = np.diff(equities) / np.maximum(equities[:-1], 1e-9)
        sd = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
        sharpe_like = float(returns.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0
        half = max(1, len(returns) // 2)
        early = float(np.mean(returns[:half])) if len(returns) else 0.0
        recent = float(np.mean(returns[-half:])) if len(returns) else 0.0
        decay = max(0.0, (early - recent) / (abs(early) + 1e-6)) if early > recent else 0.0
        decay = min(3.0, decay)
        return {"live_sharpe": sharpe_like, "net_expectancy": float(np.mean(returns)), "decay": decay}

    def metrics(self, strategy_id: str, stage: str) -> dict[str, Any]:
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            rows = list(conn.execute(
                "SELECT ts,pnl,equity,drawdown FROM strategy_performance WHERE strategy_id=%s AND stage=%s ORDER BY ts",
                (strategy_id, stage),
            ).fetchall())
            fills = conn.execute(
                """SELECT COUNT(*) AS trades,COUNT(DISTINCT DATE(ts)) AS days,COALESCE(SUM(fees),0) AS fees
                   FROM fills WHERE strategy_id=%s AND (
                     COALESCE(NULLIF(payload->>'stage',''), CASE WHEN venue='PAPER' THEN 'PAPER' ELSE 'LEGACY_LIVE' END)=%s
                     OR ((payload->>'stage') IS NULL AND %s IN ('CANARY','LIVE','SCALED') AND venue<>'PAPER')
                   )""",
                (strategy_id, stage, stage),
            ).fetchone()
        key = "paper" if stage == "PAPER" else "canary" if stage == "CANARY" else "live"
        ret = self._return_metrics(rows)
        max_drawdown = max([float(x["drawdown"] or 0) for x in rows] or [0.0])
        return {
            f"{key}_trades": int(fills["trades"] or 0),
            f"{key}_days": int(fills["days"] or 0),
            f"{key}_drawdown": max_drawdown,
            "fees_paid": float(fills["fees"] or 0),
            **ret,
        }
