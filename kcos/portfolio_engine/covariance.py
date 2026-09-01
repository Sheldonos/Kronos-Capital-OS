import numpy as np
class CovarianceEstimator:
    def shrink(self,returns,shrinkage=.2):
        x=np.asarray(returns,dtype=float); sample=np.cov(x,rowvar=False); diag=np.diag(np.diag(sample)); return (1-shrinkage)*sample+shrinkage*diag
