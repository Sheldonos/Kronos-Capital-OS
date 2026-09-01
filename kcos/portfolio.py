from __future__ import annotations

from .models import OrderIntent


class PortfolioEngine:
    """Converts alpha into target economic exposure, then trades only the delta."""

    def intent_from_signal(
        self,
        signal,
        equity: float,
        mark: float,
        current_qty: float = 0.0,
        allocation_weight: float = 1.0,
        max_target_fraction: float = 0.10,
        min_rebalance_fraction: float = 0.02,
    ):
        if mark <= 0 or signal.score == 0 or signal.confidence <= 0:
            target_qty = 0.0
        else:
            direction = 1.0 if signal.score > 0 else -1.0
            edge_scale = min(1.0, abs(float(signal.expected_return)) / 0.01)
            target_fraction = min(max_target_fraction, max_target_fraction * float(signal.confidence) * edge_scale)
            target_fraction *= max(0.0, min(1.0, float(allocation_weight)))
            target_qty = direction * equity * target_fraction / mark
        delta = target_qty - current_qty
        min_delta = max(abs(target_qty) * min_rebalance_fraction, 1e-10)
        if abs(delta) < min_delta:
            return None
        reduces_absolute = abs(target_qty) < abs(current_qty) and (target_qty == 0 or target_qty * current_qty >= 0)
        return OrderIntent(
            strategy_id=signal.strategy_id,
            venue=signal.venue,
            instrument=signal.instrument,
            asset_class=signal.asset_class,
            side="BUY" if delta > 0 else "SELL",
            qty=abs(delta),
            reference_price=mark,
            stop_distance_pct=2.0,
            confidence=signal.confidence,
            reduce_only=reduces_absolute,
            metadata={
                "expected_return": signal.expected_return,
                "target_qty": target_qty,
                "current_qty": current_qty,
                "allocation_weight": allocation_weight,
            },
        )
