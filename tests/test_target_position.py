import asyncio
from kcos.execution.paper import PaperVenue
from kcos.models import Signal
from kcos.portfolio import PortfolioEngine


def test_target_position_trades_delta_only():
    signal = Signal("S", "PAPER", "BTC-USD", "CRYPTO", 1.0, 1.0, 0.01, 6)
    p = PortfolioEngine()
    first = p.intent_from_signal(signal, 1000, 100, current_qty=0, allocation_weight=1)
    assert first is not None
    target = first.metadata["target_qty"]
    second = p.intent_from_signal(signal, 1000, 100, current_qty=target, allocation_weight=1)
    assert second is None


def test_paper_broker_is_stateful():
    signal = Signal("S", "PAPER", "X", "EQUITY", 1.0, 1.0, 0.01, 6)
    engine = PortfolioEngine()
    venue = PaperVenue(1000, fee_bps=0, slippage_bps=0)
    intent = engine.intent_from_signal(signal, 1000, 100, current_qty=0, allocation_weight=1)
    fill = asyncio.run(venue.place_order(intent, intent.qty))
    assert fill["signed_qty"] > 0
    venue.mark("X", 110)
    state = asyncio.run(venue.account_state())
    assert state.equity > 1000
    assert len(state.positions) == 1
