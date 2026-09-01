from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row


class MarketRepository:
    """Durable compact market state used to recover after process/context loss."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    def upsert_last_event(self, event) -> None:
        sql = """
        INSERT INTO latest_market_state(instrument,venue,asset_class,ts,price,bid,ask,volume,payload)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
        ON CONFLICT(instrument) DO UPDATE SET
          venue=excluded.venue,asset_class=excluded.asset_class,ts=excluded.ts,price=excluded.price,
          bid=excluded.bid,ask=excluded.ask,volume=excluded.volume,payload=excluded.payload
        """
        payload = {
            "metadata": getattr(event, "metadata", {}),
        }
        with psycopg.connect(self.dsn) as conn:
            conn.execute(sql, (event.instrument, event.venue, event.asset_class, event.ts, event.price, event.bid, event.ask, event.volume, json.dumps(payload, default=str)))

    def insert_bar(self, instrument: str, venue: str, asset_class: str, bar: dict[str, Any], interval_seconds: int = 60) -> None:
        sql = """
        INSERT INTO market_bars(instrument,venue,asset_class,interval_seconds,ts,open,high,low,close,volume)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT(instrument,interval_seconds,ts) DO UPDATE SET
          open=excluded.open,high=excluded.high,low=excluded.low,close=excluded.close,volume=excluded.volume
        """
        with psycopg.connect(self.dsn) as conn:
            conn.execute(sql, (instrument, venue, asset_class, interval_seconds, bar["timestamp"], bar["open"], bar["high"], bar["low"], bar["close"], bar.get("volume", 0)))

    def recent_bars(self, instrument: str, limit: int = 512, interval_seconds: int = 60) -> list[dict[str, Any]]:
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            rows = conn.execute(
                """SELECT ts AS timestamp,open,high,low,close,volume FROM market_bars
                   WHERE instrument=%s AND interval_seconds=%s ORDER BY ts DESC LIMIT %s""",
                (instrument, interval_seconds, limit),
            ).fetchall()
        return list(reversed(rows))

    def latest_states(self, limit: int = 5000) -> list[dict[str, Any]]:
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            return list(conn.execute(
                "SELECT instrument,venue,asset_class,ts,price,bid,ask,volume,payload FROM latest_market_state ORDER BY ts DESC LIMIT %s",
                (limit,),
            ).fetchall())
