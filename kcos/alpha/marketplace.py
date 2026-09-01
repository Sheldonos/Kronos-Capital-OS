from dataclasses import dataclass
@dataclass(slots=True)
class AlphaScore: strategy_id:str; score:float; allocation_weight:float; reason:str
class AlphaMarketplace:
    def rank(self,strategies):
        raw=[]
        for s in strategies:
            m=s.metrics; sharpe=float(m.get('live_sharpe',m.get('oos_sharpe',0))); dd=abs(float(m.get('max_drawdown',0)))
            expectancy=float(m.get('net_expectancy',0)); stability=float(m.get('stability',.5)); decay=float(m.get('decay',0))
            governance=float(m.get('governance_multiplier',1.0)); score=((max(0,sharpe)*.35+max(0,expectancy)*20*.35+stability*.3)/(1+dd*4+max(0,decay))*max(0,min(1,governance))) if s.enabled else 0
            raw.append((s,score))
        denom=sum(x for _,x in raw) or 1.0
        return [AlphaScore(s.strategy_id,score,score/denom,'risk-adjusted competition') for s,score in sorted(raw,key=lambda z:z[1],reverse=True)]
