import heapq,time
class PriorityScheduler:
    def __init__(self): self.q=[]; self.seq=0
    def submit(self,priority,item): self.seq+=1; heapq.heappush(self.q,(priority,self.seq,item))
    def pop(self): return heapq.heappop(self.q)[-1] if self.q else None
    def __len__(self): return len(self.q)
