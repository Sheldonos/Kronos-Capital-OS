from kcos.market_graph import MarketGraph
def test_cross_asset_relationship():
    g=MarketGraph()
    for i in range(60): g.update_return('A',i/10000); g.update_return('B',i/10000+.0001)
    assert g.correlation('A','B')>.9
