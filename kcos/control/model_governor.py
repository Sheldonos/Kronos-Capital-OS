class ModelGovernor:
    """Evidence-driven allocation haircut/disable policy for degraded strategies/models."""

    def allocation_multiplier(self, calibration_haircut=1.0, drift_score=0.0):
        return max(0.0, min(1.0, float(calibration_haircut) * (1.0 - min(1.0, max(0.0, float(drift_score))))))

    def should_disable(self, drift_score, calibration_haircut=1.0):
        return float(drift_score) > 1.0 or float(calibration_haircut) < 0.3

    def strategy_action(self, stage: str, metrics: dict):
        trades_key = "paper_trades" if stage == "PAPER" else "canary_trades" if stage == "CANARY" else "live_trades"
        dd_key = "paper_drawdown" if stage == "PAPER" else "canary_drawdown" if stage == "CANARY" else "live_drawdown"
        trades = int(metrics.get(trades_key, 0) or 0)
        drawdown = float(metrics.get(dd_key, 0) or 0)
        decay = float(metrics.get("decay", 0) or 0)
        expectancy = float(metrics.get("net_expectancy", 0) or 0)
        if stage == "CANARY" and drawdown >= 0.05:
            return "DEMOTE", "canary_drawdown"
        if stage in {"LIVE", "SCALED"} and drawdown >= 0.10:
            return "DEMOTE", "live_drawdown"
        if stage in {"CANARY", "LIVE", "SCALED"} and trades >= 30 and expectancy < 0 and decay >= 0.5:
            return "DEMOTE", "statistical_decay"
        return "KEEP", "within_governance_limits"
