from .domain import LifecycleState
class LifecycleManager:
    ORDER=list(LifecycleState)
    def __init__(self,state=LifecycleState.NEWBORN): self.state=state
    def promote(self,target):
        target=LifecycleState(target)
        if self.ORDER.index(target)>self.ORDER.index(self.state)+1: raise ValueError('lifecycle promotions must be sequential')
        self.state=target; return self.state
    def demote(self,target): self.state=LifecycleState(target); return self.state
