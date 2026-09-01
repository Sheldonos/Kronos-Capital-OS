from datetime import datetime,timezone
class ConnectorWatchdog:
    def __init__(self,max_age=6): self.max_age=max_age; self.last={}
    def seen(self,name,ts=None): self.last[name]=ts or datetime.now(timezone.utc)
    def stale(self,required):
        now=datetime.now(timezone.utc); return [n for n in required if n not in self.last or (now-self.last[n]).total_seconds()>self.max_age]
