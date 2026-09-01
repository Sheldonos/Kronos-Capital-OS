import numpy as np
class VolatilityModel:
    def ewma(self,prices,lam=.94):
        p=np.asarray(prices,dtype=float)
        if len(p)<3:return 0.0
        r=np.diff(np.log(np.maximum(p,1e-12))); var=r[0]**2
        for x in r[1:]: var=lam*var+(1-lam)*x*x
        return float(np.sqrt(max(var,0)))
    def realized(self,prices):
        p=np.asarray(prices,dtype=float); return float(np.std(np.diff(np.log(np.maximum(p,1e-12))),ddof=1)) if len(p)>2 else 0.0
