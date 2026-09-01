import numpy as np
class FactorModel:
    def momentum(self,prices,lookback=20):
        if len(prices)<2:return 0.0
        x=prices[-min(len(prices),lookback):]; return float(x[-1]/x[0]-1)
    def reversal(self,prices,lookback=10): return -self.momentum(prices,lookback)
    def zscore(self,prices,lookback=60):
        x=np.asarray(prices[-min(len(prices),lookback):],dtype=float)
        if len(x)<3 or np.std(x)==0:return 0.0
        return float((x[-1]-np.mean(x))/np.std(x))
