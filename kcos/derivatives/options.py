from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean


@dataclass(slots=True)
class OptionQuote:
    contract_id: str
    underlying: str
    strike: float
    time_to_expiry_years: float
    option_type: str  # CALL / PUT
    bid: float
    ask: float
    volume: float = 0.0
    open_interest: float = 0.0
    metadata: dict | None = None

    @property
    def mid(self) -> float:
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2.0
        return max(self.bid, self.ask, 0.0)


class OptionAnalytics:
    """Dependency-light Black-Scholes analytics for option intelligence/research.

    KCOS does not use option-implied dispersion as a substitute for the deterministic
    portfolio risk engine. These analytics help choose/compare trade expressions only.
    """

    @staticmethod
    def _cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    @staticmethod
    def _pdf(x: float) -> float:
        return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

    @classmethod
    def greeks(cls, spot: float, strike: float, t: float, rate: float, vol: float, option_type: str) -> dict[str, float]:
        spot, strike, t, vol = map(float, (spot, strike, t, vol))
        if min(spot, strike, t, vol) <= 0:
            raise ValueError("spot, strike, time and volatility must be positive")
        cp = 1.0 if str(option_type).upper() == "CALL" else -1.0
        d1 = (math.log(spot / strike) + (rate + 0.5 * vol * vol) * t) / (vol * math.sqrt(t))
        d2 = d1 - vol * math.sqrt(t)
        nd1 = cls._cdf(cp * d1)
        nd2 = cls._cdf(cp * d2)
        price = cp * (spot * nd1 - strike * math.exp(-rate * t) * nd2)
        delta = cp * nd1
        gamma = cls._pdf(d1) / (spot * vol * math.sqrt(t))
        vega = spot * cls._pdf(d1) * math.sqrt(t)
        theta = -(spot * cls._pdf(d1) * vol) / (2 * math.sqrt(t)) - cp * rate * strike * math.exp(-rate * t) * cls._cdf(cp * d2)
        rho = cp * strike * t * math.exp(-rate * t) * cls._cdf(cp * d2)
        return {"price": price, "delta": delta, "gamma": gamma, "vega": vega, "theta": theta, "rho": rho}

    @classmethod
    def implied_vol(cls, market_price: float, spot: float, strike: float, t: float, rate: float, option_type: str, iterations: int = 80) -> float | None:
        market_price = float(market_price)
        if market_price <= 0 or min(spot, strike, t) <= 0:
            return None
        lo, hi = 1e-4, 5.0
        for _ in range(iterations):
            mid = (lo + hi) / 2.0
            model = cls.greeks(spot, strike, t, rate, mid, option_type)["price"]
            if model > market_price:
                hi = mid
            else:
                lo = mid
        iv = (lo + hi) / 2.0
        return iv if 1e-4 <= iv <= 5.0 else None

    @classmethod
    def surface(cls, chain: list[OptionQuote], spot: float, rate: float = 0.0) -> dict:
        rows = []
        for q in chain:
            iv = cls.implied_vol(q.mid, spot, q.strike, q.time_to_expiry_years, rate, q.option_type)
            if iv is None:
                continue
            g = cls.greeks(spot, q.strike, q.time_to_expiry_years, rate, iv, q.option_type)
            rows.append({"quote": q, "iv": iv, **g})
        if not rows:
            return {"available": False, "reason": "no_valid_option_quotes"}
        expiries = sorted({round(r["quote"].time_to_expiry_years, 8) for r in rows})
        term = []
        for t in expiries:
            subset = [r for r in rows if round(r["quote"].time_to_expiry_years, 8) == t]
            atm = min(subset, key=lambda r: abs(r["quote"].strike - spot))
            term.append({"t": t, "atm_iv": atm["iv"]})
        puts = [r["iv"] for r in rows if r["quote"].option_type.upper() == "PUT" and r["quote"].strike < spot]
        calls = [r["iv"] for r in rows if r["quote"].option_type.upper() == "CALL" and r["quote"].strike > spot]
        skew = (mean(puts) - mean(calls)) if puts and calls else 0.0
        return {
            "available": True,
            "rows": rows,
            "term_structure": term,
            "front_atm_iv": term[0]["atm_iv"] if term else None,
            "put_call_skew": skew,
        }


class TradeExpressionEngine:
    """Select a bounded option expression without authorizing naked short-option risk."""

    def propose(self, expected_return: float, confidence: float, horizon_years: float, surface: dict | None, max_risk_dollars: float) -> dict:
        if confidence < 0.60 or abs(expected_return) < 0.002:
            return {"expression": "NO_TRADE", "reason": "insufficient_directional_edge"}
        direction = "BULLISH" if expected_return > 0 else "BEARISH"
        if not surface or not surface.get("available") or not surface.get("front_atm_iv"):
            return {"expression": "UNDERLYING", "direction": direction, "max_risk_dollars": max_risk_dollars, "reason": "option_surface_unavailable"}
        iv = float(surface["front_atm_iv"])
        implied_move = iv * math.sqrt(max(float(horizon_years), 1e-8))
        expected_move = abs(float(expected_return))
        # High implied volatility favors a defined-risk vertical over paying for all of the vol.
        if iv >= 0.60 or expected_move <= implied_move:
            expression = "CALL_DEBIT_SPREAD" if expected_return > 0 else "PUT_DEBIT_SPREAD"
        else:
            expression = "LONG_CALL" if expected_return > 0 else "LONG_PUT"
        return {
            "expression": expression,
            "direction": direction,
            "max_risk_dollars": max(0.0, float(max_risk_dollars)),
            "implied_move": implied_move,
            "expected_move": expected_move,
            "naked_short_options_allowed": False,
        }
