from __future__ import annotations

import uuid
from dataclasses import dataclass

from ..models import AccountState, ConnectorState, Position


@dataclass(slots=True)
class _PaperPosition:
    qty: float = 0.0
    avg_price: float = 0.0
    mark_price: float = 0.0


class PaperVenue:
    """Stateful paper broker with cash, positions, fees and mark-to-market equity."""

    name = "paper"

    def __init__(self, equity=1000.0, fee_bps=1.0, slippage_bps=0.5):
        self.starting_equity = float(equity)
        self.cash = float(equity)
        self.fee_bps = float(fee_bps)
        self.slippage_bps = float(slippage_bps)
        self.positions: dict[str, _PaperPosition] = {}
        self.orders = []
        self.peak_equity = float(equity)
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0


    def restore(self, positions, cash: float):
        self.cash = float(cash)
        self.positions = {}
        for row in positions:
            if str(row.get("venue", "")).upper() != "PAPER":
                continue
            symbol = str(row["instrument"])
            self.positions[symbol] = _PaperPosition(
                qty=float(row.get("qty", 0) or 0),
                avg_price=float(row.get("avg_price", 0) or 0),
                mark_price=float(row.get("avg_price", 0) or 0),
            )
        self.peak_equity = max(self.starting_equity, self._equity())

    async def health(self):
        return ConnectorState.CONNECTED

    def mark(self, instrument: str, price: float):
        pos = self.positions.setdefault(instrument, _PaperPosition())
        pos.mark_price = float(price)

    def _equity(self) -> float:
        return self.cash + sum(p.qty * p.mark_price for p in self.positions.values())

    async def account_state(self):
        eq = self._equity()
        self.peak_equity = max(self.peak_equity, eq)
        positions = [
            Position("PAPER", symbol, p.qty, p.mark_price or p.avg_price, p.avg_price, (p.mark_price - p.avg_price) * p.qty)
            for symbol, p in self.positions.items() if abs(p.qty) > 1e-12
        ]
        gross = sum(abs(p.qty * (p.mark_price or p.avg_price)) for p in self.positions.values())
        return AccountState(eq, self.cash, gross, self.daily_pnl, self.weekly_pnl, self.peak_equity, positions)

    async def place_order(self, intent, approved_qty):
        qty = abs(float(approved_qty))
        signed = qty if intent.side.upper() == "BUY" else -qty
        slip = self.slippage_bps / 10000.0
        price = float(intent.reference_price) * (1 + slip if signed > 0 else 1 - slip)
        notional = signed * price
        fee = abs(notional) * self.fee_bps / 10000.0
        pos = self.positions.setdefault(intent.instrument, _PaperPosition(mark_price=price))
        old_qty = pos.qty
        new_qty = old_qty + signed
        if old_qty == 0 or old_qty * signed > 0:
            denom = abs(old_qty) + abs(signed)
            pos.avg_price = (abs(old_qty) * pos.avg_price + abs(signed) * price) / max(denom, 1e-12)
        elif old_qty * new_qty < 0:
            pos.avg_price = price
        elif abs(new_qty) < 1e-12:
            pos.avg_price = 0.0
        pos.qty = new_qty
        pos.mark_price = float(intent.reference_price)
        self.cash -= notional + fee
        fill = {
            "status": "FILLED_SIMULATED",
            "fill_id": uuid.uuid4().hex,
            "client_order_id": intent.metadata.get("client_order_id") or uuid.uuid4().hex,
            "venue": "PAPER",
            "instrument": intent.instrument,
            "side": intent.side,
            "qty": qty,
            "signed_qty": signed,
            "price": price,
            "fees": fee,
            "strategy_id": intent.strategy_id,
        }
        self.orders.append(fill)
        return fill

    async def cancel_all(self):
        return None
