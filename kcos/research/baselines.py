import numpy as np
class Baselines:
    def persistence(self,returns): return np.sign(np.r_[0,returns[:-1]])*returns
    def momentum(self,returns,lookback=5):
        r=np.asarray(returns); out=np.zeros_like(r)
        for i in range(lookback,len(r)): out[i]=np.sign(np.sum(r[i-lookback:i]))*r[i]
        return out
    def random(self,returns,seed=7):
        rng=np.random.default_rng(seed); return rng.choice([-1,1],len(returns))*np.asarray(returns)
