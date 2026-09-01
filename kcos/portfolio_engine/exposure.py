from collections import defaultdict
class ExposureBook:
    def summarize(self,positions,instruments):
        by_asset=defaultdict(float); by_venue=defaultdict(float); gross=0
        for p in positions:
            inst=instruments.get(p.instrument); n=abs(p.qty*p.mark_price*(inst.contract_multiplier if inst else 1)); gross+=n
            by_asset[(inst.asset_class if inst else 'UNKNOWN')]+=n; by_venue[p.venue]+=n
        return {'gross':gross,'by_asset_class':dict(by_asset),'by_venue':dict(by_venue)}
