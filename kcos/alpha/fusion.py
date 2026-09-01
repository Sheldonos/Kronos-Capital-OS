from ..models import Signal
class AlphaFusion:
    def signal(self,strategy_id,venue,instrument,asset_class,forecast,regime_multiplier=1.0,cost_bps=0.0):
        net=forecast.expected_return-cost_bps/10000.0
        score=net*forecast.confidence*regime_multiplier
        return Signal(strategy_id,venue,instrument,asset_class,score,forecast.confidence,net,forecast.horizon_seconds,
                      metadata={'forecast_source':forecast.source,'regime_multiplier':regime_multiplier,'cost_bps':cost_bps})
