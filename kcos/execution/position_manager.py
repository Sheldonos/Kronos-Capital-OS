from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row


class StrategyPositionManager:
    """Persistent strategy-level position, cost basis, realized P&L and risk ledger."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    def get(self, strategy_id: str, venue: str, instrument: str) -> dict[str, float]:
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            row = conn.execute(
                "SELECT qty,avg_price,risk_dollars,realized_pnl,capital_base FROM strategy_positions WHERE strategy_id=%s AND venue=%s AND instrument=%s",
                (strategy_id, venue, instrument),
            ).fetchone()
        return dict(row) if row else {"qty": 0.0, "avg_price": 0.0, "risk_dollars": 0.0, "realized_pnl": 0.0, "capital_base": 0.0}

    def current_qty(self, strategy_id: str, venue: str, instrument: str) -> float:
        return float(self.get(strategy_id, venue, instrument)["qty"])

    def apply_fill(self, fill: dict[str, Any], stop_distance_pct: float = 2.0, capital_base: float = 0.0) -> dict[str, float]:
        signed = float(fill.get("signed_qty", fill.get("qty", 0)))
        if "signed_qty" not in fill and str(fill.get("side", "BUY")).upper() == "SELL":
            signed = -abs(signed)
        strategy_id, venue, instrument = fill["strategy_id"], fill["venue"], fill["instrument"]
        price = float(fill.get("price", 0))
        with psycopg.connect(self.dsn) as conn:
            current = conn.execute(
                "SELECT qty,avg_price,realized_pnl,capital_base FROM strategy_positions WHERE strategy_id=%s AND venue=%s AND instrument=%s FOR UPDATE",
                (strategy_id, venue, instrument),
            ).fetchone()
            old_qty = float(current[0]) if current else 0.0
            old_avg = float(current[1]) if current else 0.0
            realized_total = float(current[2]) if current else 0.0
            base = max(float(current[3]) if current else 0.0, float(capital_base))
            new_qty = old_qty + signed
            realized_increment = 0.0
            new_avg = old_avg
            if old_qty == 0 or old_qty * signed > 0:
                denom = abs(old_qty) + abs(signed)
                new_avg = (abs(old_qty) * old_avg + abs(signed) * price) / max(denom, 1e-12)
            else:
                closing = min(abs(old_qty), abs(signed))
                realized_increment = closing * (price - old_avg) * (1.0 if old_qty > 0 else -1.0)
                if abs(new_qty) < 1e-12:
                    new_avg = 0.0
                elif old_qty * new_qty < 0:
                    new_avg = price
            realized_total += realized_increment - float(fill.get("fees", 0) or 0)
            risk = abs(new_qty * price) * max(float(stop_distance_pct), 0.0) / 100.0
            conn.execute(
                """INSERT INTO strategy_positions(strategy_id,venue,instrument,qty,avg_price,risk_dollars,realized_pnl,capital_base,updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,now())
                   ON CONFLICT(strategy_id,venue,instrument) DO UPDATE SET
                     qty=excluded.qty,avg_price=excluded.avg_price,risk_dollars=excluded.risk_dollars,
                     realized_pnl=excluded.realized_pnl,capital_base=excluded.capital_base,updated_at=now()""",
                (strategy_id, venue, instrument, new_qty, new_avg, risk, realized_total, base),
            )
        return {"qty": new_qty, "avg_price": new_avg, "realized_increment": realized_increment, "realized_pnl": realized_total, "risk_dollars": risk, "capital_base": base}

    def strategy_pnl(self, strategy_id: str, marks: dict[str, float]) -> dict[str, float]:
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            rows = conn.execute(
                "SELECT instrument,qty,avg_price,realized_pnl,capital_base FROM strategy_positions WHERE strategy_id=%s",
                (strategy_id,),
            ).fetchall()
        realized = sum(float(x["realized_pnl"]) for x in rows)
        unrealized = sum(float(x["qty"]) * (float(marks.get(x["instrument"], x["avg_price"])) - float(x["avg_price"])) for x in rows)
        base = max([float(x["capital_base"]) for x in rows] or [0.0])
        return {"realized": realized, "unrealized": unrealized, "pnl": realized + unrealized, "capital_base": base}

    def snapshot(self) -> dict[tuple[str, str, str], dict[str, float]]:
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            rows = conn.execute("SELECT strategy_id,venue,instrument,qty,avg_price,risk_dollars,realized_pnl,capital_base FROM strategy_positions").fetchall()
        return {(r["strategy_id"], r["venue"], r["instrument"]): dict(r) for r in rows}

    def aggregate_positions(self, venue: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT venue,instrument,SUM(qty) AS qty,MAX(avg_price) AS avg_price,SUM(risk_dollars) AS risk_dollars FROM strategy_positions"
        args: tuple[Any, ...] = ()
        if venue:
            query += " WHERE venue=%s"
            args = (venue,)
        query += " GROUP BY venue,instrument"
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            return list(conn.execute(query, args).fetchall())

    def risk_used(self) -> float:
        with psycopg.connect(self.dsn) as conn:
            return float(conn.execute("SELECT COALESCE(SUM(risk_dollars),0) FROM strategy_positions").fetchone()[0])

    def venue_notional(self, venue: str) -> float:
        with psycopg.connect(self.dsn) as conn:
            return float(conn.execute(
                "SELECT COALESCE(SUM(ABS(qty*avg_price)),0) FROM strategy_positions WHERE venue=%s",
                (venue,),
            ).fetchone()[0])
