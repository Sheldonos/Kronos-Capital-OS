from collections import defaultdict
class AttributionEngine:
    def explain(self,trade):
        return {'forecast':float(trade.get('forecast_component',0)),'regime':float(trade.get('regime_component',0)),
                'execution':float(trade.get('execution_component',0)),'sizing':float(trade.get('sizing_component',0)),
                'event':float(trade.get('event_component',0))}
    def aggregate(self,records):
        out=defaultdict(float)
        for r in records:
            for k,v in self.explain(r).items():out[k]+=v
        return dict(out)
