from collections import deque
import numpy as np
class DriftDetector:
    def __init__(self,window=50): self.live=deque(maxlen=window); self.reference=None
    def set_reference(self,values): self.reference=float(np.mean(values)) if values else 0
    def add(self,value): self.live.append(float(value))
    def score(self):
        if self.reference is None or len(self.live)<10:return 0.0
        return abs(float(np.mean(self.live))-self.reference)/(abs(self.reference)+1e-6)
