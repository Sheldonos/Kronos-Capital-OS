from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from ..models import ConnectorState, MarketEvent


class DatabentoFeed:
    name = "databento"

    def __init__(self, api_key, subscription):
        self.api_key = api_key
        self.subscription = subscription
        self.connected = False
        self.replaying = False
        self.last_error = None
        self.last_ts: datetime | None = None
        self.symbol_map: dict[int, str] = {}

    async def health(self):
        if self.replaying:
            return ConnectorState.REPLAYING
        return ConnectorState.CONNECTED if self.connected else ConnectorState.RECONNECTING

    @staticmethod
    def _symbol_text(value):
        if isinstance(value, bytes):
            return value.decode("utf-8", "ignore").rstrip("\x00")
        return str(value).rstrip("\x00")

    @staticmethod
    def _price(record):
        for attr in ("pretty_price", "pretty_close", "price", "close"):
            value = getattr(record, attr, None)
            if value is not None:
                try:
                    px = float(value)
                    if attr in {"price", "close"} and abs(px) > 1e8:
                        px /= 1e9
                    return px
                except Exception:
                    pass
        return None

    async def run(self, on_event):
        import databento as db
        loop = asyncio.get_running_loop()

        while True:
            def sync_session():
                client = db.Live(key=self.api_key)
                kwargs = {
                    "dataset": self.subscription["dataset"],
                    "schema": self.subscription.get("schema", "trades"),
                    "stype_in": self.subscription.get("stype_in", "raw_symbol"),
                    "symbols": self.subscription["symbols"],
                }
                if self.last_ts is not None:
                    kwargs["start"] = self.last_ts.isoformat()
                    self.replaying = True
                client.subscribe(**kwargs)
                self.connected = True
                for rec in client:
                    if hasattr(db, "SymbolMappingMsg") and isinstance(rec, db.SymbolMappingMsg):
                        iid = int(getattr(getattr(rec, "hd", rec), "instrument_id", getattr(rec, "instrument_id", 0)))
                        symbol = getattr(rec, "stype_in_symbol", None) or getattr(rec, "stype_out_symbol", None)
                        if iid and symbol:
                            self.symbol_map[iid] = self._symbol_text(symbol)
                        continue
                    # System messages include replay completion/heartbeats.
                    if rec.__class__.__name__ == "SystemMsg":
                        msg = str(getattr(rec, "msg", ""))
                        if "replay" in msg.lower() and "complete" in msg.lower():
                            self.replaying = False
                        continue
                    iid = int(getattr(rec, "instrument_id", getattr(getattr(rec, "hd", rec), "instrument_id", 0)) or 0)
                    symbol = self.symbol_map.get(iid)
                    if not symbol:
                        continue
                    price = self._price(rec)
                    if price is None or price <= 0:
                        continue
                    ts_ns = getattr(rec, "ts_event", getattr(getattr(rec, "hd", rec), "ts_event", None))
                    ts = datetime.fromtimestamp(int(ts_ns) / 1e9, timezone.utc) if ts_ns else datetime.now(timezone.utc)
                    self.last_ts = ts
                    fut = asyncio.run_coroutine_threadsafe(
                        on_event(MarketEvent("DATABENTO", symbol, self.subscription.get("asset_class", "UNKNOWN"), price, ts=ts, metadata={"dataset": self.subscription["dataset"], "instrument_id": iid})),
                        loop,
                    )
                    fut.result()

            try:
                await asyncio.to_thread(sync_session)
            except asyncio.CancelledError:
                self.connected = False
                raise
            except Exception as exc:
                self.connected = False
                self.last_error = repr(exc)
                await asyncio.sleep(1.0)
