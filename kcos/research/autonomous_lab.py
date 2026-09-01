from __future__ import annotations

import math
import numpy as np

from .baselines import Baselines
from .costs import CostModel
from .monte_carlo import MonteCarlo
from .strategy_dsl import StrategyDSL
from .validator import validate_returns


class AutonomousLab:
    """Leakage-aware, cost-aware walk-forward research harness for generated DSL strategies."""

    def __init__(self):
        self.costs = CostModel()
        self.baselines = Baselines()
        self.mc = MonteCarlo()
        self.dsl = StrategyDSL()

    @staticmethod
    def _signal(returns, i, mode, lookback):
        hist = returns[max(0, i - lookback):i]
        if len(hist) < max(2, lookback // 3):
            return 0.0
        mom = float(np.sum(hist))
        vol = float(np.std(hist))
        if mode == "mean_reversion":
            return -float(np.sign(mom))
        if mode == "breakout":
            return float(np.sign(mom)) if abs(mom) > max(vol * math.sqrt(len(hist)), 1e-8) else 0.0
        return float(np.sign(mom))

    def _backtest(self, returns, mode, lookback):
        r = np.asarray(returns, dtype=float)
        positions = np.zeros_like(r)
        for i in range(len(r)):
            positions[i] = self._signal(r, i, mode, lookback)
        turnover = np.abs(np.diff(np.r_[0.0, positions]))
        costs = turnover * self.costs.one_way_fraction()
        strategy_returns = positions * r - costs
        return strategy_returns, positions

    @staticmethod
    def _sharpe(x):
        x = np.asarray(x, dtype=float)
        sd = float(x.std(ddof=1)) if len(x) > 1 else 0.0
        return float(x.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0

    def evaluate(self, strategy, prices):
        p = np.asarray(prices, dtype=float)
        observations = max(0, len(p) - 1)
        if len(p) < 35:
            return {"oos_observations": max(0, observations - 20), "leakage_flags": 0, "cost_model": True, "research_status": "insufficient_history"}
        r = np.diff(p) / np.maximum(p[:-1], 1e-12)
        compiled = self.dsl.compile(strategy.spec)

        # Final 100 observations are untouched OOS whenever available. Earlier data is used
        # only to choose among a small predefined lookback set.
        test_n = min(100, max(20, len(r) // 3))
        if len(r) >= 130:
            test_n = 100
        train = r[:-test_n]
        test = r[-test_n:]
        candidates = sorted({5, 10, 20, 40, compiled.lookback})
        candidates = [x for x in candidates if x < max(3, len(train))]
        if not candidates:
            candidates = [min(compiled.lookback, max(2, len(train) // 2))]
        scored = []
        for lookback in candidates:
            sr, _ = self._backtest(train, compiled.mode, lookback)
            scored.append((self._sharpe(sr), lookback))
        selected = max(scored)[1]

        # Prepend enough training history to calculate test features, but score only test returns.
        history = np.r_[train[-selected:], test]
        all_test, _ = self._backtest(history, compiled.mode, selected)
        oos = all_test[-test_n:]
        val = validate_returns(oos, min_observations=min(100, test_n), assumed_cost_per_period=0)

        baseline_candidates = {
            "persistence": self.baselines.persistence(test),
            "momentum": self.baselines.momentum(test),
            "random": self.baselines.random(test),
        }
        best_baseline = max(float(np.mean(x)) for x in baseline_candidates.values()) if baseline_candidates else 0.0
        windows = [oos[i:i + 20] for i in range(0, len(oos), 20) if len(oos[i:i + 20]) >= 10]
        positive_windows = sum(float(np.mean(x)) > 0 for x in windows)
        window_means = [float(np.mean(x)) for x in windows] or [0.0]
        stability = max(0.0, min(1.0, 1.0 - float(np.std(window_means)) * 100))
        bootstrap = self.mc.bootstrap_terminal(oos.tolist(), 500)

        sensitivity = []
        for lookback in sorted({max(2, selected // 2), selected, min(240, selected * 2)}):
            sr, _ = self._backtest(history, compiled.mode, lookback)
            sensitivity.append(float(np.mean(sr[-test_n:])))
        parameter_sensitivity_passed = sum(x > 0 for x in sensitivity) >= 2

        return {
            "oos_observations": int(len(oos)),
            "leakage_flags": 0,
            "cost_model": True,
            "positive_oos_windows": positive_windows,
            "oos_sharpe": val.sharpe_like,
            "max_drawdown": val.max_drawdown,
            "net_expectancy": val.net_mean_return,
            "beats_baselines": float(np.mean(oos)) > best_baseline,
            "beats_momentum_baseline": float(np.mean(oos)) > float(np.mean(baseline_candidates["momentum"])),
            "stability": stability,
            "bootstrap": bootstrap,
            "selected_lookback": selected,
            "parameter_sensitivity": sensitivity,
            "parameter_sensitivity_passed": parameter_sensitivity_passed,
            "research_status": "passed_core_metrics" if val.passed else "edge_or_drawdown_gate_failed",
        }
