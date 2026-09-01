from __future__ import annotations

from dataclasses import dataclass


ALLOWED_SIGNAL_MODES = {"trend", "mean_reversion", "breakout", "cross_asset", "ensemble"}
ALLOWED_FEATURES = {"kronos", "momentum", "reversal", "regime", "cross_asset", "volatility", "zscore", "reversal_primary"}


@dataclass(slots=True)
class CompiledStrategy:
    mode: str
    features: list[str]
    lookback: int
    entry_threshold: float
    exit_threshold: float


class StrategyDSL:
    """Small deterministic strategy language; generated text never becomes executable code."""

    def compile(self, spec: dict) -> CompiledStrategy:
        features = [x for x in spec.get("features", []) if x in ALLOWED_FEATURES]
        metadata = spec.get("metadata") or {}
        mode = str(metadata.get("signal_mode", "ensemble"))
        if mode not in ALLOWED_SIGNAL_MODES:
            raise ValueError(f"unsupported signal mode: {mode}")
        lookback = max(2, min(int(metadata.get("lookback", 20)), 240))
        entry = max(0.0, float(metadata.get("entry_threshold", 0.0)))
        exit_t = max(0.0, float(metadata.get("exit_threshold", entry * 0.5)))
        return CompiledStrategy(mode, features, lookback, entry, exit_t)

    def component_names(self, spec: dict) -> set[str]:
        c = self.compile(spec)
        names = set(c.features)
        names.discard("volatility")
        names.discard("zscore")
        names.discard("reversal_primary")
        return names
