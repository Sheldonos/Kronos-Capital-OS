from datetime import datetime, timezone
from kcos.config import Settings
from kcos.models import AccountState, OrderIntent
from kcos.risk_kernel import RiskKernel


def test_integrity_latch_blocks_new_risk_but_allows_exit():
    cfg = Settings(_env_file=None)
    account = AccountState(1000, 1000, 0, 0, 0, 1000, [])
    entry = OrderIntent("S", "IBKR", "X", "EQUITY", "BUY", 1, 100, 2, .9)
    exit_order = OrderIntent("S", "IBKR", "X", "EQUITY", "SELL", 1, 100, 2, .9, reduce_only=True)
    kernel = RiskKernel(cfg)
    assert not kernel.evaluate(entry, account, datetime.now(timezone.utc), integrity_blocked=True).approved
    assert kernel.evaluate(exit_order, account, datetime.now(timezone.utc), integrity_blocked=True).approved
