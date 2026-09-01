from kcos.trend_engine import TrendEngine
def test_trend():
    out=TrendEngine().summarize([100,101,102,103,104,105])
    assert out["micro"]["direction"]=="UP"
