from collections import defaultdict, deque
class BarStore:
    def __init__(self,maxlen=5000): self.prices=defaultdict(lambda:deque(maxlen=maxlen)); self.volumes=defaultdict(lambda:deque(maxlen=maxlen))
    def update(self,instrument,price,volume=None): self.prices[instrument].append(float(price)); self.volumes[instrument].append(None if volume is None else float(volume))
    def closes(self,instrument,n=None):
        x=list(self.prices[instrument]); return x if n is None else x[-n:]
