from collections import defaultdict
from datetime import datetime, timezone


class BarAggregator:
    def __init__(self, seconds=60):
        self.seconds = seconds
        self.current = {}
        self.completed = defaultdict(list)

    def _bucket(self, ts):
        return int(ts.timestamp()) // self.seconds * self.seconds

    def update_with_closed(self, event):
        bucket = self._bucket(event.ts)
        cur = self.current.get(event.instrument)
        closed = None
        if cur and cur["bucket"] != bucket:
            closed = cur.copy()
            self.completed[event.instrument].append(closed)
            self.current.pop(event.instrument, None)
            cur = None
        if cur is None:
            cur = {
                "bucket": bucket,
                "timestamp": datetime.fromtimestamp(bucket, timezone.utc),
                "open": event.price,
                "high": event.price,
                "low": event.price,
                "close": event.price,
                "volume": event.volume or 0.0,
            }
            self.current[event.instrument] = cur
        else:
            cur["high"] = max(cur["high"], event.price)
            cur["low"] = min(cur["low"], event.price)
            cur["close"] = event.price
            cur["volume"] += event.volume or 0.0
        return cur, closed

    def update(self, event):
        cur, _ = self.update_with_closed(event)
        return cur

    def seed(self, instrument, bars):
        self.completed[instrument].extend(list(bars))

    def bars(self, instrument, n=512):
        return self.completed[instrument][-n:]
