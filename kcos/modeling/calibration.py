import numpy as np
class CalibrationTracker:
    def __init__(self): self.records=[]
    def add(self,confidence,correct): self.records.append((float(confidence),1.0 if correct else 0.0))
    def brier(self):
        if not self.records:return None
        return float(np.mean([(p-y)**2 for p,y in self.records]))
    def haircut(self):
        b=self.brier(); return 1.0 if b is None else max(.25,min(1.0,1.0-b*2))
