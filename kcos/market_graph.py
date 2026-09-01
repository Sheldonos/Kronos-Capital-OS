from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

import numpy as np


class MarketGraph:
    """Cross-asset relationship graph over timestamp-aligned completed-bar returns.

    A relationship is never calculated by simply pairing the last N ticks from two
    markets. Sparse/closed markets are aligned on common bar timestamps first.
    """

    def __init__(self, maxlen: int = 2000):
        self.maxlen = int(maxlen)
        self.returns: dict[str, deque[tuple[int, float]]] = defaultdict(lambda: deque(maxlen=self.maxlen))
        self.events = deque(maxlen=5000)

    @staticmethod
    def _bucket(ts: datetime | int | float) -> int:
        if isinstance(ts, datetime):
            return int(ts.timestamp())
        return int(ts)

    def update_return(self, instrument: str, value: float, ts: datetime | int | float | None = None) -> None:
        dq = self.returns[instrument]
        # Live/recovered data always supplies the completed-bar timestamp. For
        # direct library use without timestamps, align observations by sequence
        # number rather than wall-clock time so two instruments updated in the
        # same logical loop remain comparable and tests are deterministic.
        bucket = (dq[-1][0] + 1 if dq else 1) if ts is None else self._bucket(ts)
        if dq and dq[-1][0] == bucket:
            dq[-1] = (bucket, float(value))
        else:
            dq.append((bucket, float(value)))

    def update_event(self, event: Any) -> None:
        self.events.append(event)

    def last_return(self, instrument: str) -> float:
        return float(self.returns[instrument][-1][1]) if self.returns[instrument] else 0.0

    def _aligned(self, a: str, b: str, window: int) -> tuple[np.ndarray, np.ndarray]:
        xa = dict(list(self.returns[a])[-window * 3 :])
        xb = dict(list(self.returns[b])[-window * 3 :])
        common = sorted(set(xa).intersection(xb))[-window:]
        if not common:
            return np.asarray([]), np.asarray([])
        return np.asarray([xa[t] for t in common], dtype=float), np.asarray([xb[t] for t in common], dtype=float)

    def correlation(self, a: str, b: str, window: int = 120) -> float | None:
        x, y = self._aligned(a, b, window)
        if len(x) < 20 or np.std(x) == 0 or np.std(y) == 0:
            return None
        return float(np.corrcoef(x, y)[0, 1])

    def lead_lag(self, a: str, b: str, max_lag: int = 12, window: int = 240) -> dict[str, float] | None:
        x, y = self._aligned(a, b, window)
        if len(x) < 40:
            return None
        best_lag, best_corr = 0, 0.0
        for lag in range(-max_lag, max_lag + 1):
            if lag < 0:
                xx, yy = x[-lag:], y[:lag]
            elif lag > 0:
                xx, yy = x[:-lag], y[lag:]
            else:
                xx, yy = x, y
            if len(xx) < 20 or np.std(xx) == 0 or np.std(yy) == 0:
                continue
            corr = float(np.corrcoef(xx, yy)[0, 1])
            if abs(corr) > abs(best_corr):
                best_lag, best_corr = lag, corr
        return {"lag": int(best_lag), "correlation": float(best_corr)}

    def neighbors(self, instrument: str, threshold: float = 0.45) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for other in list(self.returns):
            if other == instrument:
                continue
            corr = self.correlation(instrument, other)
            if corr is not None and abs(corr) >= threshold:
                out[other] = {
                    "correlation": corr,
                    "lead_lag": self.lead_lag(instrument, other),
                    "last_return": self.last_return(other),
                }
        return out
