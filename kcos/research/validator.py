from dataclasses import dataclass
import numpy as np
@dataclass(slots=True)
class ValidationResult:
    passed:bool; observations:int; net_mean_return:float; sharpe_like:float; max_drawdown:float; reason:str
def validate_returns(returns,min_observations=100,assumed_cost_per_period=0.0):
    x=np.asarray(returns,dtype=float)-assumed_cost_per_period
    if len(x)<min_observations:
        return ValidationResult(False,len(x),float(x.mean()) if len(x) else 0,0,0,"insufficient_oos_observations")
    curve=np.cumprod(1+x); peaks=np.maximum.accumulate(curve); dd=(peaks-curve)/np.maximum(peaks,1e-12)
    sd=x.std(ddof=1); sharpe=float(x.mean()/sd*np.sqrt(252)) if sd>0 else 0
    passed=bool(x.mean()>0 and sharpe>0 and dd.max(initial=0)<0.10)
    return ValidationResult(passed,len(x),float(x.mean()),sharpe,float(dd.max(initial=0)),"passed" if passed else "gate_failed")
