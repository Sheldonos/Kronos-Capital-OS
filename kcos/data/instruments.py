from __future__ import annotations
from ..domain import Instrument
class InstrumentRegistry:
    def __init__(self): self._by_id={}; self._by_symbol={}
    def register(self,x:Instrument): self._by_id[x.instrument_id]=x; self._by_symbol[(x.venue,x.symbol)]=x; return x
    def resolve(self,venue,symbol): return self._by_symbol.get((venue,symbol))
    def get(self,instrument_id): return self._by_id[instrument_id]
    def all(self,asset_class=None):
        vals=list(self._by_id.values()); return vals if not asset_class else [x for x in vals if x.asset_class==asset_class]
