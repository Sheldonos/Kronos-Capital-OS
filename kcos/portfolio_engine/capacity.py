from __future__ import annotations

from statistics import mean


class CapacityModel:
    """Conservative liquidity capacity estimate from observed bars.

    This is not a license to scale. It is an evidence gate used to keep strategies
    unscaled when the system cannot estimate how much notional the market can absorb.
    """

    BARS_PER_DAY = {"CRYPTO": 1440, "FX": 1440, "EQUITY": 390, "ETF": 390, "OPTION": 390, "FUTURE": 1380, "COMMODITY": 1380, "RATE": 1380, "INDEX": 390}

    def estimate(self, bars: list[dict], asset_class: str, max_participation: float = 0.005) -> dict:
        usable = [b for b in bars if float(b.get("close", 0) or 0) > 0 and float(b.get("volume", 0) or 0) > 0]
        if len(usable) < 60:
            return {"available": False, "reason": "insufficient_volume_history"}
        per_day = self.BARS_PER_DAY.get(str(asset_class).upper(), 390)
        sample = usable[-min(len(usable), per_day):]
        avg_dollar_per_bar = mean(float(b["close"]) * float(b["volume"]) for b in sample)
        estimated_daily_dollar_volume = avg_dollar_per_bar * per_day
        one_way_capacity = estimated_daily_dollar_volume * max(0.0001, min(float(max_participation), 0.02))
        return {
            "available": one_way_capacity > 0,
            "estimated_daily_dollar_volume": estimated_daily_dollar_volume,
            "max_one_way_notional": one_way_capacity,
            "max_participation": max_participation,
            "sample_bars": len(sample),
        }
