from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass

from .domain import StrategyRecord


@dataclass(slots=True)
class StrategySpec:
    strategy_id: str
    hypothesis_id: str
    universe: list[str]
    asset_class: str
    features: list[str]
    entry_rules: list[str]
    exit_rules: list[str]
    max_holding_seconds: int = 86400
    stage: str = "RESEARCH"
    metadata: dict | None = None


class StrategyFactory:
    def from_hypothesis(self, hypothesis_id, subject, asset_class, features, venue="PAPER", metadata=None):
        metadata = {"venue": venue, **(metadata or {})}
        sid = "STRAT-" + hashlib.sha1(f"{hypothesis_id}:{subject}:{asset_class}:{features}:{metadata}".encode()).hexdigest()[:12].upper()
        return StrategySpec(
            sid,
            hypothesis_id,
            [subject],
            asset_class,
            features,
            ["net_edge > entry_threshold", "confidence >= configured_minimum", "regime_eligible"],
            ["net_edge <= exit_threshold", "risk_reduction_required", "regime_ineligible"],
            metadata=metadata,
        )

    def variants_from_hypothesis(self, hypothesis_id, subject, asset_class, venue="PAPER"):
        templates = [
            (["kronos", "momentum", "regime", "cross_asset"], {"signal_mode": "ensemble", "lookback": 20}),
            (["kronos", "reversal", "reversal_primary", "regime", "zscore"], {"signal_mode": "mean_reversion", "lookback": 10}),
            (["momentum", "regime", "volatility"], {"signal_mode": "breakout", "lookback": 40}),
            (["cross_asset", "momentum", "regime"], {"signal_mode": "cross_asset", "lookback": 20}),
            (["momentum", "zscore", "regime"], {"signal_mode": "trend", "lookback": 60}),
            (["kronos", "momentum", "reversal", "cross_asset", "regime"], {"signal_mode": "ensemble", "lookback": 30}),
        ]
        return [self.from_hypothesis(f"{hypothesis_id}-{i}", subject, asset_class, features, venue, meta) for i, (features, meta) in enumerate(templates, 1)]

    def record(self, spec, metrics=None):
        d = asdict(spec)
        return StrategyRecord(spec.strategy_id, 1, spec.stage, spec.asset_class, spec.universe, spec.hypothesis_id, d, metrics or {})
