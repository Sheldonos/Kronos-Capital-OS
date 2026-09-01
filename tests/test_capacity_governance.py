from kcos.control.model_governor import ModelGovernor
from kcos.portfolio_engine.capacity import CapacityModel


def test_capacity_requires_real_volume_history():
    model = CapacityModel()
    assert not model.estimate([{"close": 100, "volume": 0}] * 100, "EQUITY")["available"]
    result = model.estimate([{"close": 100, "volume": 1000}] * 100, "EQUITY")
    assert result["available"]
    assert result["max_one_way_notional"] > 0


def test_model_governor_demotes_decaying_live_strategy():
    action, reason = ModelGovernor().strategy_action("LIVE", {"live_trades": 40, "live_drawdown": .02, "net_expectancy": -.001, "decay": .8})
    assert action == "DEMOTE"
    assert reason == "statistical_decay"
