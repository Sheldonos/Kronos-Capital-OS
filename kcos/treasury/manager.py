class TreasuryManager:
    def __init__(self,min_cash_buffer_pct=.10,max_venue_pct=.50): self.min_cash_buffer_pct=min_cash_buffer_pct; self.max_venue_pct=max_venue_pct
    def allocations(self,equity,venue_balances):
        deployable=equity*(1-self.min_cash_buffer_pct); cap=equity*self.max_venue_pct
        return {'deployable':deployable,'venue_caps':{v:min(cap,deployable) for v in venue_balances}}
    def may_transfer(self,*args,**kwargs): return False  # owner-governed by design
