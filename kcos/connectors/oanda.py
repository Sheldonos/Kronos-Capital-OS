from __future__ import annotations

import json
import uuid

import httpx

from ..models import AccountState, ConnectorState, MarketEvent, Position


class OandaConnector:
    name = "oanda"

    def __init__(self, base_url, stream_url, account_id, token):
        self.base_url = base_url.rstrip("/")
        self.stream_url = stream_url.rstrip("/")
        self.account_id = account_id
        self.headers = {"Authorization": f"Bearer {token}"}

    async def health(self):
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{self.base_url}/v3/accounts/{self.account_id}/summary", headers=self.headers)
            return ConnectorState.CONNECTED if r.is_success else ConnectorState.DEGRADED

    async def account_state(self):
        async with httpx.AsyncClient(timeout=10) as c:
            summary_r = await c.get(f"{self.base_url}/v3/accounts/{self.account_id}/summary", headers=self.headers)
            summary_r.raise_for_status()
            a = summary_r.json()["account"]
            eq = float(a["NAV"])
            cash = float(a.get("balance", eq))
            positions_r = await c.get(f"{self.base_url}/v3/accounts/{self.account_id}/openPositions", headers=self.headers)
            rows = positions_r.json().get("positions", []) if positions_r.is_success else []
            positions = []
            for p in rows:
                long_units = float((p.get("long") or {}).get("units", 0) or 0)
                short_units = float((p.get("short") or {}).get("units", 0) or 0)
                qty = long_units + short_units
                if abs(qty) <= 1e-12:
                    continue
                avg = float((p.get("long") if qty > 0 else p.get("short") or {}).get("averagePrice", 0) or 0)
                unreal = float(p.get("unrealizedPL", 0) or 0)
                positions.append(Position("OANDA", p["instrument"], qty, avg, avg, unreal))
            gross = float(a.get("marginUsed", 0) or 0)
            return AccountState(eq, cash, gross, 0.0, 0.0, eq, positions)

    async def place_order(self, intent, approved_qty):
        units = float(approved_qty) if intent.side == "BUY" else -float(approved_qty)
        client_order_id = intent.metadata.get("client_order_id") or f"KCOS-{uuid.uuid4().hex[:20]}"
        body = {
            "order": {
                "units": str(int(units)) if abs(units) >= 1 else str(units),
                "instrument": intent.instrument,
                "timeInForce": "FOK",
                "type": "MARKET",
                "positionFill": "DEFAULT",
                "clientExtensions": {"id": client_order_id, "tag": "KCOS"},
            }
        }
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{self.base_url}/v3/accounts/{self.account_id}/orders", headers=self.headers, json=body)
            r.raise_for_status()
            data = r.json()
        fill_tx = data.get("orderFillTransaction") or {}
        fill = None
        if fill_tx:
            fill = {
                "fill_id": str(fill_tx.get("id") or uuid.uuid4().hex),
                "client_order_id": client_order_id,
                "venue": "OANDA",
                "instrument": intent.instrument,
                "strategy_id": intent.strategy_id,
                "side": intent.side,
                "qty": abs(float(fill_tx.get("units", units))),
                "signed_qty": float(fill_tx.get("units", units)),
                "price": float(fill_tx.get("price", intent.reference_price)),
                "fees": abs(float(fill_tx.get("financing", 0) or 0)) + abs(float(fill_tx.get("commission", 0) or 0)),
            }
        return {
            "status": "FILLED" if fill else "SUBMITTED",
            "client_order_id": client_order_id,
            "venue": "OANDA",
            "instrument": intent.instrument,
            "strategy_id": intent.strategy_id,
            "fill": fill,
            "raw": data,
        }

    async def get_order_status(self, broker_order_id):
        if not broker_order_id:
            return {"status": "UNKNOWN"}
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{self.base_url}/v3/accounts/{self.account_id}/orders/{broker_order_id}", headers=self.headers)
            if r.status_code == 404:
                return {"status": "UNKNOWN", "broker_order_id": str(broker_order_id)}
            r.raise_for_status()
            data = r.json().get("order") or {}
        state = str(data.get("state") or "UNKNOWN").upper()
        status = {"FILLED": "FILLED", "CANCELLED": "CANCELLED", "CANCELED": "CANCELLED", "PENDING": "PENDING"}.get(state, state)
        return {"status": status, "broker_order_id": str(broker_order_id), "raw": data}

    async def cancel_all(self):
        cancelled = []
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{self.base_url}/v3/accounts/{self.account_id}/pendingOrders", headers=self.headers)
            if not r.is_success:
                return False
            for order in r.json().get("orders", []):
                oid = order.get("id")
                if oid:
                    cr = await c.put(f"{self.base_url}/v3/accounts/{self.account_id}/orders/{oid}/cancel", headers=self.headers)
                    if cr.is_success:
                        cancelled.append(str(oid))
        return {"cancelled": cancelled}

    async def run_prices(self, on_event, instruments):
        url = f"{self.stream_url}/v3/accounts/{self.account_id}/pricing/stream"
        while True:
            try:
                async with httpx.AsyncClient(timeout=None) as c:
                    async with c.stream("GET", url, headers=self.headers, params={"instruments": ",".join(instruments)}) as r:
                        r.raise_for_status()
                        async for line in r.aiter_lines():
                            if not line:
                                continue
                            msg = json.loads(line)
                            if msg.get("type") != "PRICE":
                                continue
                            bids, asks = msg.get("bids") or [], msg.get("asks") or []
                            if bids and asks:
                                bid, ask = float(bids[0]["price"]), float(asks[0]["price"])
                                await on_event(MarketEvent("OANDA", msg["instrument"], "FX", (bid + ask) / 2, bid=bid, ask=ask, metadata={"source": "oanda_stream"}))
            except Exception:
                import asyncio
                await asyncio.sleep(2)
