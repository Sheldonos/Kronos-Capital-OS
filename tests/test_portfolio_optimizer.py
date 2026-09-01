import numpy as np
from kcos.portfolio_engine.optimizer import PortfolioOptimizer
def test_optimizer_sums_to_one():
    w=PortfolioOptimizer().risk_adjusted_weights([.1,.05],[[.2,.01],[.01,.1]],max_weight=.8); assert abs(float(w.sum())-1)<1e-8 and np.all(w>=0)
