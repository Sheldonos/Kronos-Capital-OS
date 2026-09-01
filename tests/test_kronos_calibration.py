import pytest
from datetime import datetime, timedelta, timezone

pandas = pytest.importorskip("pandas", reason="pandas not installed; skip Kronos calibration tests")
from kcos.modeling.kronos_service import KronosInferenceService


def bars(n, start=100.0, step=1.0):
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        {
            "timestamp": ts + timedelta(minutes=i),
            "open": start + step * i,
            "high": start + step * i,
            "low": start + step * i,
            "close": start + step * i,
            "volume": 10.0,
        }
        for i in range(n)
    ]


def test_pending_kronos_forecast_updates_calibration_once():
    svc = KronosInferenceService("m", "t", min_bars=1, pred_len=2)
    history = bars(5, step=1.0)
    svc.pending["BTC"] = {
        "reference_close": history[2]["close"],
        "expected_return": 0.02,
        "raw_confidence": 0.8,
        "target_bar_count": 5,
        "created_at": 0,
    }
    assert svc._observe_outcome("BTC", history) is True
    assert svc.calibration["BTC"].records == [(0.8, 1.0)]
    assert svc._observe_outcome("BTC", history) is False
    assert len(svc.calibration["BTC"].records) == 1


def test_wrong_forecast_reduces_future_confidence_haircut():
    svc = KronosInferenceService("m", "t", min_bars=1, pred_len=1)
    history = bars(4, start=100.0, step=-1.0)
    svc.pending["ETH"] = {
        "reference_close": 102.0,
        "expected_return": 0.02,
        "raw_confidence": 0.9,
        "target_bar_count": 4,
        "created_at": 0,
    }
    assert svc._observe_outcome("ETH", history) is True
    assert svc.calibration["ETH"].records == [(0.9, 0.0)]
    assert svc.calibration["ETH"].haircut() < 1.0
