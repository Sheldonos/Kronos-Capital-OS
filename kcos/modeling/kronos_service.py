from __future__ import annotations

import asyncio
import time

import pandas as pd

from .calibration import CalibrationTracker
from ..kronos_adapter import KronosAdapter


class KronosInferenceService:
    """Asynchronous Kronos inference with empirical confidence calibration.

    Forecasts are cached for the low-latency decision path.  Each forecast also
    creates a pending calibration observation that is resolved after ``pred_len``
    completed bars.  The realized directional outcome is fed into the
    ``CalibrationTracker`` exactly once, allowing subsequent confidence values to
    be haircutted when historical forecast confidence proves over-optimistic.
    """

    def __init__(
        self,
        model,
        tokenizer,
        device="cpu",
        min_bars=64,
        interval_seconds=60,
        pred_len=12,
    ):
        self.adapter = KronosAdapter(model, tokenizer, device)
        self.min_bars = min_bars
        self.interval = interval_seconds
        self.pred_len = pred_len
        self.cache = {}
        self.last_run = {}
        self.inflight = set()
        self.calibration = {}
        self.pending = {}

    def cached_component(self, instrument):
        item = self.cache.get(instrument)
        if not item:
            return None
        return {
            "expected_return": item["expected_return"],
            "confidence": item["confidence"],
        }

    def _observe_outcome(self, instrument, bars):
        """Resolve a pending forecast once its horizon has completed.

        Returns ``True`` when a calibration sample was recorded.  A zero realized
        move counts as correct only for an effectively zero expected move; this
        avoids rewarding directional forecasts for flat outcomes.
        """
        pending = self.pending.get(instrument)
        if not pending or len(bars) < pending["target_bar_count"]:
            return False

        latest_close = float(bars[pending["target_bar_count"] - 1]["close"])
        reference_close = max(float(pending["reference_close"]), 1e-12)
        realized_return = latest_close / reference_close - 1.0
        expected_return = float(pending["expected_return"])

        eps = 1e-12
        if abs(expected_return) <= eps:
            correct = abs(realized_return) <= eps
        else:
            correct = (expected_return > 0 and realized_return > 0) or (
                expected_return < 0 and realized_return < 0
            )

        tracker = self.calibration.setdefault(instrument, CalibrationTracker())
        tracker.add(float(pending["raw_confidence"]), correct)
        self.pending.pop(instrument, None)
        return True

    async def maybe_schedule(self, instrument, bars):
        bars = list(bars)
        self._observe_outcome(instrument, bars)

        if len(bars) < self.min_bars or instrument in self.inflight:
            return
        now = time.time()
        if now - self.last_run.get(instrument, 0) < self.interval:
            return
        self.inflight.add(instrument)
        self.last_run[instrument] = now
        asyncio.create_task(self._run(instrument, bars))

    async def _run(self, instrument, bars):
        try:
            df = pd.DataFrame(bars).set_index("timestamp")
            last = df.index[-1]
            future = pd.date_range(
                last, periods=self.pred_len + 1, freq="1min", inclusive="right"
            ).to_series(index=None)
            result = await asyncio.to_thread(
                self.adapter.forecast, df, future, self.pred_len, 5
            )

            tracker = self.calibration.setdefault(instrument, CalibrationTracker())
            haircut = tracker.haircut()
            expected_return = float(result["expected_return"])
            raw_confidence = max(0.05, min(0.9, 0.5 + abs(expected_return) * 5))
            calibrated_confidence = max(0.05, min(0.9, raw_confidence * haircut))

            self.cache[instrument] = {
                "expected_return": expected_return,
                "confidence": calibrated_confidence,
                "raw_confidence": raw_confidence,
                "calibration_haircut": haircut,
                "path": result.get("path", []),
                "ts": time.time(),
            }
            self.pending[instrument] = {
                "reference_close": float(df["close"].iloc[-1]),
                "expected_return": expected_return,
                "raw_confidence": raw_confidence,
                "target_bar_count": len(bars) + self.pred_len,
                "created_at": time.time(),
            }
        except Exception as exc:
            self.cache[instrument] = {
                "expected_return": 0.0,
                "confidence": 0.0,
                "error": repr(exc),
                "ts": time.time(),
            }
        finally:
            self.inflight.discard(instrument)
