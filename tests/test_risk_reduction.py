from datetime import datetime, timezone, timedelta
from kcos.config import Settings
from kcos.models import AccountState, OrderIntent
from kcos.risk_kernel import RiskKernel


def test_reduce_only_can_exit_when_state_is_stale_and_limits_are_exceeded():
    cfg = Settings(_env_file=None)
    account = AccountState(1000, 100, 5000, -100, -100, 2000, [])
    intent = OrderIntent("S", "PAPER", "X", "EQUITY", "SELL", 50, 100, 2, 0.1, reduce_only=True)
    decision = RiskKernel(cfg).evaluate(intent, account, datetime.now(timezone.utc)-timedelta(seconds=60), emergency_stop=True, aggregate_open_risk_dollars=9999, venue_notional_dollars=9999)
    assert decision.approved
    assert decision.approved_qty == 50
