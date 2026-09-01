from __future__ import annotations

import json
from typing import Any

import psycopg
from psycopg.rows import dict_row


def _connect(dsn: str, *, row_factory=None) -> psycopg.Connection:
    """Open a new psycopg3 connection.  Row-factory is applied when provided.

    All call sites obtain a connection via ``with _connect(self.dsn) as conn``
    which commits on exit and closes on ``__exit__``.  This helper centralises
    the single keyword that differs between plain and dict-row callers.
    """
    kwargs: dict[str, Any] = {}
    if row_factory is not None:
        kwargs["row_factory"] = row_factory
    return psycopg.connect(dsn, **kwargs)


class MemoryStore:
    """Durable institutional memory and evidence ledger.

    The database, not model context, is authoritative. All methods are deliberately
    deterministic and reconstructable from persisted records.

    Connection strategy: each public method acquires a short-lived connection via
    ``_connect()``.  psycopg3 reuses OS-level TCP connections through the server's
    idle-connection recycling; this is adequate for the ~1 call/second rate of a
    single KCOS instance.  For higher throughput, migrate to
    ``psycopg_pool.ConnectionPool`` (add ``psycopg-pool>=3.1`` to dependencies).
    """

    def __init__(self, dsn: str):
        self.dsn = dsn

    def health(self) -> bool:
        try:
            with _connect(self.dsn) as conn:
                return conn.execute("SELECT 1").fetchone()[0] == 1
        except Exception:
            return False

    def audit(self, instance_id: str, event_type: str, payload: dict[str, Any]) -> None:
        sql = "INSERT INTO audit_events(event_type,instance_id,payload) VALUES (%s,%s,%s::jsonb)"
        with _connect(self.dsn) as conn:
            conn.execute(sql, (event_type, instance_id, json.dumps(payload, default=str)))

    def list_audit(self, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        with _connect(self.dsn, row_factory=dict_row) as conn:
            rows = conn.execute(
                "SELECT ts,event_type,instance_id,payload FROM audit_events ORDER BY ts DESC LIMIT %s",
                (limit,),
            ).fetchall()
        return list(rows)

    def remember(self, memory_type: str, subject: str, summary: str, evidence=None, confidence: float = 0.5) -> None:
        sql = "INSERT INTO memories(memory_type,subject,summary,evidence,confidence) VALUES (%s,%s,%s,%s::jsonb,%s)"
        with _connect(self.dsn) as conn:
            conn.execute(sql, (memory_type, subject, summary, json.dumps(evidence or {}, default=str), confidence))

    def recall(self, subject: str, limit: int = 8) -> list[dict[str, Any]]:
        sql = "SELECT ts,memory_type,subject,summary,evidence,confidence FROM memories WHERE subject=%s AND (expires_at IS NULL OR expires_at>now()) ORDER BY ts DESC LIMIT %s"
        with _connect(self.dsn, row_factory=dict_row) as conn:
            return list(conn.execute(sql, (subject, limit)).fetchall())

    def recall_many(self, subjects: list[str], limit_each: int = 8) -> dict[str, list[dict[str, Any]]]:
        subjects = sorted({str(x) for x in subjects if x})
        if not subjects:
            return {}
        sql = """
        SELECT ts,memory_type,subject,summary,evidence,confidence FROM (
          SELECT ts,memory_type,subject,summary,evidence,confidence,
                 ROW_NUMBER() OVER(PARTITION BY subject ORDER BY ts DESC) AS rn
          FROM memories
          WHERE subject=ANY(%s) AND (expires_at IS NULL OR expires_at>now())
        ) ranked WHERE rn<=%s ORDER BY subject,ts DESC
        """
        out = {x: [] for x in subjects}
        with _connect(self.dsn, row_factory=dict_row) as conn:
            for row in conn.execute(sql, (subjects, max(1, int(limit_each)))).fetchall():
                out[str(row["subject"])].append(dict(row))
        return out

    def recent_memories(self, limit: int = 100) -> list[dict[str, Any]]:
        with _connect(self.dsn, row_factory=dict_row) as conn:
            return list(conn.execute(
                "SELECT ts,memory_type,subject,summary,evidence,confidence FROM memories ORDER BY ts DESC LIMIT %s",
                (max(1, min(int(limit), 1000)),),
            ).fetchall())

    def hypotheses(self, limit: int = 100) -> list[dict[str, Any]]:
        with _connect(self.dsn, row_factory=dict_row) as conn:
            return list(conn.execute(
                "SELECT hypothesis_id,created_at,subject,statement,counter_hypothesis,priority,status,evidence FROM hypotheses ORDER BY created_at DESC LIMIT %s",
                (max(1, min(int(limit), 1000)),),
            ).fetchall())

    def upsert_hypothesis(self, hypothesis_id: str, subject: str, statement: str, counter: str, priority: float, evidence: dict | None = None) -> None:
        sql = """
        INSERT INTO hypotheses(hypothesis_id,subject,statement,counter_hypothesis,priority,evidence)
        VALUES (%s,%s,%s,%s,%s,%s::jsonb)
        ON CONFLICT(hypothesis_id) DO UPDATE SET
          priority=excluded.priority,evidence=excluded.evidence
        """
        with _connect(self.dsn) as conn:
            conn.execute(sql, (hypothesis_id, subject, statement, counter, priority, json.dumps(evidence or {}, default=str)))

    def record_decision(self, decision_id: str, world_version: int, instrument: str | None, context: dict, decision: dict, outcome: dict | None = None) -> None:
        sql = """
        INSERT INTO decisions(decision_id,world_version,instrument,context,decision,outcome)
        VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb)
        ON CONFLICT(decision_id) DO NOTHING
        """
        with _connect(self.dsn) as conn:
            conn.execute(sql, (
                decision_id, world_version, instrument,
                json.dumps(context, default=str), json.dumps(decision, default=str), json.dumps(outcome, default=str) if outcome is not None else None,
            ))

    def paper_cash_from_fills(self, initial_capital: float) -> float:
        with _connect(self.dsn) as conn:
            row = conn.execute(
                """SELECT COALESCE(SUM(
                    COALESCE(NULLIF(payload->>'signed_qty','')::double precision,
                             CASE WHEN UPPER(COALESCE(payload->>'side','BUY'))='SELL' THEN -qty ELSE qty END) * price
                    + COALESCE(fees,0)
                ),0) FROM fills WHERE venue='PAPER'"""
            ).fetchone()
        return float(initial_capital) - float(row[0] or 0.0)

    def live_fill_venues(self) -> list[str]:
        with _connect(self.dsn) as conn:
            rows = conn.execute("SELECT DISTINCT UPPER(venue) FROM fills WHERE venue IS NOT NULL AND UPPER(venue)<>'PAPER' ORDER BY 1").fetchall()
        return [str(x[0]) for x in rows]

    def fills(self, strategy_id: str | None = None, limit: int = 1000) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 10000))
        where, args = "", []
        if strategy_id:
            where, args = " WHERE strategy_id=%s", [strategy_id]
        with _connect(self.dsn, row_factory=dict_row) as conn:
            rows = conn.execute(
                f"SELECT fill_id,ts,venue,instrument,strategy_id,qty,price,fees,payload FROM fills{where} ORDER BY ts DESC LIMIT %s",
                tuple(args + [limit]),
            ).fetchall()
        return list(rows)

    def record_fill(self, fill: dict[str, Any]) -> bool:
        sql = """
        INSERT INTO fills(fill_id,venue,instrument,strategy_id,qty,price,fees,payload)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
        ON CONFLICT(fill_id) DO NOTHING
        RETURNING fill_id
        """
        with _connect(self.dsn) as conn:
            row = conn.execute(sql, (
                fill["fill_id"], fill.get("venue"), fill.get("instrument"), fill.get("strategy_id"),
                float(fill.get("qty", 0)), float(fill.get("price", 0)), float(fill.get("fees", 0)), json.dumps(fill, default=str),
            )).fetchone()
        return bool(row)
