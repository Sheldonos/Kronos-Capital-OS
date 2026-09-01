from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

import psycopg
from psycopg.rows import dict_row


PENDING_STATUSES = {"CREATED", "SUBMITTED", "PENDING", "REQUIRES_CONFIRMATION", "PARTIALLY_FILLED"}


class OrderManager:
    """Persistent idempotent order ledger.

    The client id is deterministic for a given decision/strategy/instrument so retries
    reconstruct rather than duplicate the same intended action.
    """

    def __init__(self, dsn: str | None = None):
        self.dsn = dsn
        self.pending: dict[str, dict[str, Any]] = {}
        self.completed: dict[str, dict[str, Any]] = {}

    def client_id(self, strategy_id: str, instrument: str, decision_id: str | None = None) -> str:
        seed = decision_id or uuid.uuid4().hex
        digest = hashlib.sha256(f"{seed}:{strategy_id}:{instrument}".encode()).hexdigest()[:16]
        return f"KCOS-{digest}"

    def has_pending(self, strategy_id: str, venue: str, instrument: str) -> bool:
        if not self.dsn:
            return any(
                x.get("strategy_id") == strategy_id and x.get("venue") == venue and x.get("instrument") == instrument
                for x in self.pending.values()
            )
        with psycopg.connect(self.dsn) as conn:
            row = conn.execute(
                "SELECT 1 FROM orders WHERE strategy_id=%s AND venue=%s AND instrument=%s AND status=ANY(%s) LIMIT 1",
                (strategy_id, venue, instrument, list(PENDING_STATUSES)),
            ).fetchone()
        return bool(row)

    def register_intent(self, decision_id: str, intent, approved_qty: float, client_order_id: str) -> str:
        order_id = uuid.uuid4().hex
        payload = {
            "order_id": order_id,
            "client_order_id": client_order_id,
            "decision_id": decision_id,
            "strategy_id": intent.strategy_id,
            "venue": intent.venue,
            "instrument": intent.instrument,
            "side": intent.side,
            "requested_qty": intent.qty,
            "approved_qty": approved_qty,
            "status": "CREATED",
        }
        if not self.dsn:
            self.pending[client_order_id] = payload
            return order_id
        sql = """
        INSERT INTO orders(order_id,client_order_id,decision_id,strategy_id,venue,instrument,side,requested_qty,approved_qty,status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'CREATED')
        ON CONFLICT(client_order_id) DO NOTHING
        """
        with psycopg.connect(self.dsn) as conn:
            conn.execute(sql, (order_id, client_order_id, decision_id, intent.strategy_id, intent.venue, intent.instrument, intent.side, intent.qty, approved_qty))
        return order_id

    def update(self, client_order_id: str, status: str, response: dict | None = None) -> None:
        status = str(status).upper()
        if not self.dsn:
            obj = self.pending.pop(client_order_id, {"client_order_id": client_order_id})
            obj.update({"status": status, "response": response or {}})
            if status in PENDING_STATUSES:
                self.pending[client_order_id] = obj
            else:
                self.completed[client_order_id] = obj
            return
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                "UPDATE orders SET status=%s,response=%s::jsonb,updated_at=now() WHERE client_order_id=%s",
                (status, json.dumps(response or {}, default=str), client_order_id),
            )

    def list_pending(self, limit: int = 200) -> list[dict[str, Any]]:
        if not self.dsn:
            return list(self.pending.values())[:limit]
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            return list(conn.execute(
                "SELECT * FROM orders WHERE status=ANY(%s) ORDER BY created_at LIMIT %s",
                (list(PENDING_STATUSES), limit),
            ).fetchall())
