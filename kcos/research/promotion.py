from ..domain import StrategyStage


class PromotionEngine:
    ORDER = list(StrategyStage)

    def next_stage(self, current, metrics):
        c = StrategyStage(current)
        if c == StrategyStage.RESEARCH and metrics.get("leakage_flags", 0) == 0 and metrics.get("oos_observations", 0) >= 100:
            return StrategyStage.WALK_FORWARD
        if c == StrategyStage.WALK_FORWARD:
            robust = metrics.get("beats_baselines", metrics.get("beats_momentum_baseline", False))
            bootstrap = metrics.get("bootstrap") or {}
            if metrics.get("positive_oos_windows", 0) >= 3 and metrics.get("cost_model", False) and robust and metrics.get("parameter_sensitivity_passed", False) and float(bootstrap.get("median", 0)) > 0:
                return StrategyStage.PAPER
        if c == StrategyStage.PAPER and metrics.get("paper_trades", 0) >= 50 and metrics.get("paper_days", 0) >= 14 and metrics.get("paper_drawdown", 1) < .08 and metrics.get("paper_execution_parity", True):
            return StrategyStage.CANARY
        if c == StrategyStage.CANARY and metrics.get("canary_trades", 0) >= 30 and metrics.get("canary_drawdown", 1) < .05 and metrics.get("live_authority_ready", False):
            return StrategyStage.LIVE
        if c == StrategyStage.LIVE and metrics.get("live_trades", 0) >= 100 and metrics.get("net_expectancy", 0) > 0 and metrics.get("capacity_estimated", False):
            return StrategyStage.SCALED
        return c

    def demote(self, current, reason):
        if reason in {"risk_breach", "integrity_failure"}:
            return StrategyStage.RETIRED
        if reason in {"decay", "execution_parity_failure"}:
            return StrategyStage.PAPER
        if reason == "data_quality_failure":
            return StrategyStage.RESEARCH
        return StrategyStage(current)
