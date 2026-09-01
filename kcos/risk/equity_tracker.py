from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import psycopg


class EquityTracker:
    """Venue-neutral daily/weekly loss and peak-equity tracker."""

    def __init__(self, dsn: str, persist_interval: float = 60.0):
        self.dsn = dsn
        self.persist_interval = persist_interval
        self.last_write: dict[str, float] = {}

    def decorate(self, venue: str, account):
        now = datetime.now(timezone.utc)
        if time.time() - self.last_write.get(venue, 0) >= self.persist_interval:
            with psycopg.connect(self.dsn) as conn:
                conn.execute(
                    "INSERT INTO account_equity_snapshots(venue,equity,cash) VALUES (%s,%s,%s)",
                    (venue, account.equity, account.cash),
                )
            self.last_write[venue] = time.time()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = day_start - timedelta(days=day_start.weekday())
        with psycopg.connect(self.dsn) as conn:
            daily = conn.execute(
                "SELECT equity FROM account_equity_snapshots WHERE venue=%s AND ts>=%s ORDER BY ts ASC LIMIT 1",
                (venue, day_start),
            ).fetchone()
            weekly = conn.execute(
                "SELECT equity FROM account_equity_snapshots WHERE venue=%s AND ts>=%s ORDER BY ts ASC LIMIT 1",
                (venue, week_start),
            ).fetchone()
            peak = conn.execute(
                "SELECT COALESCE(MAX(equity),%s) FROM account_equity_snapshots WHERE venue=%s",
                (account.equity, venue),
            ).fetchone()
        account.daily_pnl = account.equity - float(daily[0] if daily else account.equity)
        account.weekly_pnl = account.equity - float(weekly[0] if weekly else account.equity)
        account.peak_equity = max(float(peak[0] if peak else account.equity), account.equity)
        return account
