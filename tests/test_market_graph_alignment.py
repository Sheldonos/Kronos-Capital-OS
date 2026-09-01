from kcos.market_graph import MarketGraph


def test_real_timestamps_require_overlap():
    g = MarketGraph()
    for i in range(30):
        g.update_return("A", i / 10000, 1000 + i)
        g.update_return("B", i / 10000, 2000 + i)
    assert g.correlation("A", "B") is None
