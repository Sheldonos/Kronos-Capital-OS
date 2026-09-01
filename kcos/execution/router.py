from __future__ import annotations

import asyncio


class ExecutionRouter:
    def __init__(self, mapping=None):
        self.venues = {}
        self.mapping = mapping or {}
        self.registration_errors = {}

    def register(self, name, venue):
        self.venues[name.upper()] = venue

    def map_asset_class(self, asset_class, venue_name):
        self.mapping[asset_class.upper()] = venue_name.upper()

    def get(self, name):
        key = name.upper()
        if key not in self.venues:
            raise KeyError(f"No execution venue registered for {name}")
        return self.venues[key]

    def for_asset_class(self, asset_class, paper=False):
        if paper:
            return self.get("PAPER")
        name = self.mapping.get(asset_class.upper())
        if not name:
            raise KeyError(f"No execution mapping for asset class {asset_class}")
        return self.get(name)

    async def health_snapshot(self):
        async def probe(name, venue):
            try:
                state = await asyncio.wait_for(venue.health(), timeout=5)
                return name, {"state": getattr(state, "value", str(state)), "detail": "authenticated/available"}
            except Exception as exc:
                return name, {"state": "FAILED", "detail": repr(exc)}
        pairs = await asyncio.gather(*(probe(name, venue) for name, venue in self.venues.items()))
        out = dict(pairs)
        for name, error in self.registration_errors.items():
            out[name] = {"state": "FAILED", "detail": error}
        return out

    async def cancel_all(self):
        results = {}
        for name, venue in self.venues.items():
            try:
                results[name] = await venue.cancel_all()
            except Exception as exc:
                results[name] = {"error": repr(exc)}
        return results
