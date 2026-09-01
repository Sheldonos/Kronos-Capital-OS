import numpy as np
class MonteCarlo:
    def bootstrap_terminal(self,returns,paths=1000,seed=42):
        r=np.asarray(returns,dtype=float)
        if not len(r): return {'p05':0,'median':0,'p95':0}
        rng=np.random.default_rng(seed); terminals=[]
        for _ in range(paths): terminals.append(float(np.prod(1+rng.choice(r,len(r),replace=True))-1))
        return {'p05':float(np.quantile(terminals,.05)),'median':float(np.median(terminals)),'p95':float(np.quantile(terminals,.95))}
