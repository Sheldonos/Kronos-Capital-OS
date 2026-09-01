class CostModel:
    def __init__(self, commission_bps=.5, spread_bps=1.0, slippage_bps=1.0):
        self.commission_bps = commission_bps
        self.spread_bps = spread_bps
        self.slippage_bps = slippage_bps

    def one_way_fraction(self):
        return (self.commission_bps + self.spread_bps / 2 + self.slippage_bps) / 10000.0

    def round_trip_fraction(self, turnover=1.0):
        return turnover * self.one_way_fraction() * 2
