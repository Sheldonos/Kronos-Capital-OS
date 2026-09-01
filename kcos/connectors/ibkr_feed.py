from __future__ import annotations

import asyncio
import time

import httpx

from ..models import ConnectorState, MarketEvent


class IbkrSnapshotFeed:
    """1-second top-of-book snapshot fallback for configured IBKR conids.

    Databento or another streaming feed can be preferred for research. This adapter
    ensures IBKR-only installs can still satisfy the <=6s decision-state contract.
    """

    name = "ibkr_market_data"

    def __init__(self, base_url: str, instruments: list[dict], bearer_token: str | None = None, verify_tls: bool = False, interval: float = 1.0):
        self.base_url = base_url.rstrip("/")
        self.instruments = instruments
        self.verify_tls = verify_tls
        self.interval = interval
        self.headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else {}
        self.connected = False
        self.last_error = None

    async def health(self):
        return ConnectorState.CONNECTED if self.connected else ConnectorState.RECONNECTING

    async def run(self, on_event):
        if not self.instruments:
            return
        by_conid = {str(x["conid"]): x for x in self.instruments}
        conids = ",".join(by_conid)
        fields = "31,84,86"
        async with httpx.AsyncClient(verify=self.verify_tls, timeout=5) as client:
            # First request warms the subscription per IBKR behavior.
            try:
                await client.get(f"{self.base_url}/iserver/marketdata/snapshot", headers=self.headers, params={"conids": conids, "fields": fields})
            except Exception:
                pass
            while True:
                started = time.monotonic()
                try:
                    r = await client.get(f"{self.base_url}/iserver/marketdata/snapshot", headers=self.headers, params={"conids": conids, "fields": fields})
                    r.raise_for_status()
                    rows = r.json()
                    self.connected = True
                    for row in rows if isinstance(rows, list) else []:
                        conid = str(row.get("conid") or row.get("conidEx", "")).split("@", 1)[0]
                        spec = by_conid.get(conid)
                        if not spec:
                            continue
                        last = row.get("31")
                        bid, ask = row.get("84"), row.get("86")
                        try:
                            price = float(str(last).replace(",", "")) if last not in (None, "") else (float(bid) + float(ask)) / 2
                        except Exception:
                            continue
                        await on_event(MarketEvent("IBKR", spec["symbol"], spec["asset_class"], price, bid=float(bid) if bid else None, ask=float(ask) if ask else None, metadata={"conid": int(conid), "source": "ibkr_snapshot"}))
                except asyncio.CancelledError:
                    self.connected = False
                    raise
                except Exception as exc:
                    self.connected = False
                    self.last_error = repr(exc)
                await asyncio.sleep(max(0.0, self.interval - (time.monotonic() - started)))
