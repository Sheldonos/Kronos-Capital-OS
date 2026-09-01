from kcos.strategy_factory import StrategyFactory
def test_falsifiable_variants():
    xs=StrategyFactory().variants_from_hypothesis('H','BTC','CRYPTO'); assert len(xs)>=3 and len({x.strategy_id for x in xs})==len(xs)
