class KillSwitch:
    def __init__(self): self.reasons=set()
    @property
    def active(self): return bool(self.reasons)
    def trip(self,reason): self.reasons.add(reason)
    def clear(self,reason=None): self.reasons.clear() if reason is None else self.reasons.discard(reason)
