import numpy as np
class PortfolioOptimizer:
    def risk_adjusted_weights(self,expected_returns,cov,max_weight=.25):
        mu=np.asarray(expected_returns,dtype=float); C=np.asarray(cov,dtype=float)
        if len(mu)==0:return np.array([])
        try: raw=np.linalg.solve(C+np.eye(len(mu))*1e-8,mu)
        except Exception: raw=mu.copy()
        raw=np.maximum(raw,0)
        if raw.sum()==0:return np.ones(len(mu))/len(mu)
        w=raw/raw.sum(); w=np.minimum(w,max_weight); return w/(w.sum() or 1)
