"""TEST-02 — Regression test for paper_cash_from_fills sign convention.

Tests the cash reconstruction arithmetic directly without requiring a live
database or psycopg installation, by extracting the formula used in
MemoryStore.paper_cash_from_fills and verifying its sign semantics.

Formula (from kcos/memory.py):
    cash = initial_capital - SUM(signed_qty * price + fees)

where signed_qty is positive for BUY and negative for SELL.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Pure-Python implementation of the cash formula — no DB required.
# ---------------------------------------------------------------------------

def _paper_cash(initial_capital: float, fills: list[dict]) -> float:
    """Replicate the SQL formula from MemoryStore.paper_cash_from_fills.

    For each fill:
      cost = signed_qty * price + fees
    cash = initial_capital - SUM(cost)
    """
    total_cost = 0.0
    for f in fills:
        signed_qty = f.get("signed_qty")
        if signed_qty is None:
            side = str(f.get("side", "BUY")).upper()
            qty = float(f.get("qty", 0))
            signed_qty = qty if side == "BUY" else -qty
        price = float(f.get("price", 0))
        fees = float(f.get("fees", 0))
        total_cost += float(signed_qty) * price + fees
    return float(initial_capital) - total_cost


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_buy_fill_decreases_cash():
    """BUY: positive signed_qty → cash goes out."""
    fills = [{"signed_qty": 10.0, "price": 50.0, "fees": 0.0}]
    result = _paper_cash(100_000.0, fills)
    assert result == 100_000.0 - 500.0, f"got {result}"


def test_sell_fill_increases_cash():
    """SELL: negative signed_qty → cash comes in."""
    fills = [{"signed_qty": -10.0, "price": 50.0, "fees": 0.0}]
    result = _paper_cash(100_000.0, fills)
    assert result == 100_000.0 + 500.0, f"got {result}"


def test_fees_always_reduce_cash():
    """Fees are always subtracted from cash regardless of side."""
    buy_fills = [{"signed_qty": 1.0, "price": 100.0, "fees": 5.0}]
    sell_fills = [{"signed_qty": -1.0, "price": 100.0, "fees": 5.0}]
    buy_cash = _paper_cash(10_000.0, buy_fills)
    sell_cash = _paper_cash(10_000.0, sell_fills)
    assert buy_cash == 10_000.0 - 100.0 - 5.0
    assert sell_cash == 10_000.0 + 100.0 - 5.0


def test_zero_fills_returns_initial_capital():
    """No fills → cash unchanged."""
    assert _paper_cash(50_000.0, []) == 50_000.0


def test_fallback_side_field_produces_same_result():
    """When signed_qty is absent the side field drives sign."""
    explicit = [{"signed_qty": -5.0, "price": 20.0, "fees": 0.0}]
    implicit = [{"side": "SELL", "qty": 5.0, "price": 20.0, "fees": 0.0}]
    assert _paper_cash(10_000.0, explicit) == _paper_cash(10_000.0, implicit)


def test_multiple_fills_compose_correctly():
    """Round trip: buy then sell the same position returns to initial capital."""
    fills = [
        {"signed_qty": 10.0, "price": 50.0, "fees": 0.0},   # buy 10 @ 50
        {"signed_qty": -10.0, "price": 50.0, "fees": 0.0},  # sell 10 @ 50
    ]
    assert _paper_cash(100_000.0, fills) == 100_000.0
