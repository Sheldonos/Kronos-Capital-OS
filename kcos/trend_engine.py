import numpy as np
class TrendEngine:
    WINDOWS = {"micro":5, "tactical":20, "swing":60, "structural":240}
    def summarize(self, closes):
        if len(closes)<2: return {}
        arr=np.asarray(closes,dtype=float); out={}
        for name,w in self.WINDOWS.items():
            x=arr[-min(len(arr),w):]
            if len(x)<2: continue
            ret=x[-1]/x[0]-1
            rets=np.diff(np.log(np.maximum(x,1e-12)))
            out[name]={"return":float(ret),"volatility":float(np.std(rets)) if len(rets) else 0.0,
                       "direction":"UP" if ret>0 else "DOWN" if ret<0 else "FLAT"}
        return out
