import numpy as np
class TailRisk:
    def var_es(self,returns,alpha=.05):
        r=np.asarray(returns,dtype=float)
        if not len(r):return {'var':0.0,'expected_shortfall':0.0}
        q=float(np.quantile(r,alpha)); tail=r[r<=q]; return {'var':-q,'expected_shortfall':-float(tail.mean()) if len(tail) else -q}
