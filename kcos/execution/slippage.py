class SlippageModel:
    def estimate_bps(self,spread_bps,order_notional,adv_notional=None,volatility=.01):
        impact=0 if not adv_notional else min(100,(order_notional/max(adv_notional,1))*10000*.1)
        return float(max(0,spread_bps/2+impact+volatility*100))
