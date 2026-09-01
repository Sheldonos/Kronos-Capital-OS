from __future__ import annotations

from datetime import datetime, timezone

from .models import RiskDecision


class RiskKernel:
    """Deterministic, non-self-modifying capital governor.

    User-configured limits may be *stricter* than these constitutional ceilings but
    never looser. This is enforced here as well as in the GUI/API so headless or
    malformed configuration cannot bypass the safety envelope.
    """

    HARD_CEILINGS = {
        "max_risk_per_trade_pct": 2.0,
        "max_aggregate_open_risk_pct": 10.0,
        "hard_drawdown_stop_pct": 25.0,
        "max_gross_leverage": 3.0,
        "max_venue_exposure_pct": 75.0,
        "max_single_asset_notional_pct": 50.0,
    }

    def __init__(self, cfg):
        self.cfg = cfg

    def _limit(self, name: str) -> float:
        configured = float(getattr(self.cfg, name))
        ceiling = self.HARD_CEILINGS.get(name)
        return min(configured, ceiling) if ceiling is not None else configured

    def evaluate(
        self,
        intent,
        account,
        market_ts,
        emergency_stop: bool = False,
        aggregate_open_risk_dollars: float = 0.0,
        venue_notional_dollars: float = 0.0,
        integrity_blocked: bool = False,
    ):
        now = datetime.now(timezone.utc)
        if emergency_stop and not intent.reduce_only:
            return RiskDecision(False, "emergency_stop")
        if integrity_blocked and not intent.reduce_only:
            return RiskDecision(False, "integrity_blocked")

        age = (now - market_ts).total_seconds()
        max_age = min(float(self.cfg.max_decision_staleness_seconds), 6.0)
        if age > max_age and not intent.reduce_only:
            return RiskDecision(False, f"stale_market_state:{age:.2f}s")
        if intent.confidence < float(self.cfg.min_signal_confidence) and not intent.reduce_only:
            return RiskDecision(False, "signal_confidence_below_floor")
        if account.equity <= 0:
            return RiskDecision(False, "non_positive_equity")

        # Risk-reducing orders must be able to flatten exposure even when the book is
        # already outside normal entry ceilings. They are still blocked by invalid
        # quantities/prices, but entry sizing, confidence, stale-state and leverage
        # ceilings do not prevent an exit.
        if intent.reduce_only:
            qty = abs(float(intent.qty))
            if qty <= 0 or float(intent.reference_price) <= 0:
                return RiskDecision(False, "invalid_reduce_only_order")
            return RiskDecision(True, "approved_reduce_only", qty, 0.0)

        drawdown = max(0.0, (account.peak_equity - account.equity) / max(account.peak_equity, 1e-9) * 100.0)
        if drawdown >= self._limit("hard_drawdown_stop_pct") and not intent.reduce_only:
            return RiskDecision(False, f"hard_drawdown_stop:{drawdown:.2f}%")
        if account.daily_pnl <= -(float(self.cfg.max_daily_loss_pct) / 100.0) * account.equity and not intent.reduce_only:
            return RiskDecision(False, "daily_loss_breaker")
        if account.weekly_pnl <= -(float(self.cfg.max_weekly_loss_pct) / 100.0) * account.equity and not intent.reduce_only:
            return RiskDecision(False, "weekly_loss_breaker")

        max_trade_risk = account.equity * self._limit("max_risk_per_trade_pct") / 100.0
        stop_per_unit = max(abs(intent.reference_price) * max(intent.stop_distance_pct, 0.0001) / 100.0, 1e-8)
        risk_qty = max_trade_risk / stop_per_unit

        max_asset_notional = account.equity * self._limit("max_single_asset_notional_pct") / 100.0
        notional_qty = max_asset_notional / max(abs(intent.reference_price), 1e-8)
        qty = min(abs(intent.qty), risk_qty, notional_qty)
        if qty <= 0:
            return RiskDecision(False, "zero_approved_quantity")

        if not intent.reduce_only:
            risk_room = account.equity * self._limit("max_aggregate_open_risk_pct") / 100.0 - max(0.0, aggregate_open_risk_dollars)
            qty = min(qty, max(0.0, risk_room) / stop_per_unit)
            if qty <= 0:
                return RiskDecision(False, "aggregate_open_risk_ceiling")

            venue_room = account.equity * self._limit("max_venue_exposure_pct") / 100.0 - max(0.0, venue_notional_dollars)
            qty = min(qty, max(0.0, venue_room) / max(abs(intent.reference_price), 1e-8))
            if qty <= 0:
                return RiskDecision(False, "venue_exposure_ceiling")

            gross_room = account.equity * self._limit("max_gross_leverage") - max(0.0, account.gross_exposure)
            qty = min(qty, max(0.0, gross_room) / max(abs(intent.reference_price), 1e-8))
            if qty <= 0:
                return RiskDecision(False, "gross_leverage_ceiling")

        risk_dollars = qty * stop_per_unit
        return RiskDecision(True, "approved", qty, risk_dollars)
