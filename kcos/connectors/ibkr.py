from __future__ import annotations

import httpx

from ..models import AccountState, ConnectorState, Position


class IbkrConnector:
    name = "ibkr"

    def __init__(self, base_url, account_id, bearer_token=None, verify_tls=False):
        self.base_url = base_url.rstrip("/")
        self.account_id = account_id
        self.verify_tls = verify_tls
        self.headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else {}

    async def health(self):
        async with httpx.AsyncClient(verify=self.verify_tls, timeout=5) as client:
            r = await client.get(f"{self.base_url}/iserver/auth/status", headers=self.headers)
            return ConnectorState.CONNECTED if r.is_success and r.json().get("authenticated") else ConnectorState.DEGRADED

    @staticmethod
    def _amount(summary, key, default=0.0):
        value = summary.get(key, default)
        if isinstance(value, dict):
            value = value.get("amount", default)
        try:
            return float(value or default)
        except Exception:
            return float(default)

    async def account_state(self):
        async with httpx.AsyncClient(verify=self.verify_tls, timeout=10) as client:
            summary_r = await client.get(f"{self.base_url}/portfolio/{self.account_id}/summary", headers=self.headers)
            summary_r.raise_for_status()
            summary = summary_r.json()
            equity = self._amount(summary, "netliquidation")
            cash = self._amount(summary, "totalcashvalue", equity)
            daily_pnl = self._amount(summary, "dpl", 0.0)
            positions = []
            page = 0
            while page < 20:
                r = await client.get(f"{self.base_url}/portfolio/{self.account_id}/positions/{page}", headers=self.headers)
                if not r.is_success:
                    break
                rows = r.json()
                if not isinstance(rows, list) or not rows:
                    break
                for p in rows:
                    qty = float(p.get("position", 0) or 0)
                    if abs(qty) <= 1e-12:
                        continue
                    symbol = str(p.get("ticker") or p.get("contractDesc") or p.get("conid"))
                    mark = float(p.get("mktPrice", 0) or 0)
                    avg = float(p.get("avgCost", 0) or 0)
                    unreal = float(p.get("unrealizedPnl", 0) or 0)
                    positions.append(Position("IBKR", symbol, qty, mark, avg, unreal, metadata={"conid": p.get("conid")}))
                page += 1
            gross = sum(abs(p.qty * p.mark_price) for p in positions)
            return AccountState(equity, cash, gross, daily_pnl, 0.0, max(equity, 1.0), positions)

    async def place_order(self, intent, approved_qty):
        conid = intent.metadata.get("conid")
        if not conid:
            raise ValueError("IBKR requires resolved conid in order metadata")
        client_order_id = intent.metadata.get("client_order_id")
        order = {
            "acctId": self.account_id,
            "conid": int(conid),
            "orderType": "MKT",
            "side": intent.side,
            "quantity": approved_qty,
            "tif": "DAY",
        }
        if client_order_id:
            order["cOID"] = client_order_id
        async with httpx.AsyncClient(verify=self.verify_tls, timeout=10) as client:
            r = await client.post(f"{self.base_url}/iserver/account/{self.account_id}/orders", headers=self.headers, json={"orders": [order]})
            r.raise_for_status()
            data = r.json()
        # IBKR may return a reply ID requiring confirmation for an order warning.
        first = data[0] if isinstance(data, list) and data else data
        reply_id = first.get("id") if isinstance(first, dict) and first.get("message") else None
        order_id = first.get("order_id") if isinstance(first, dict) else None
        return {
            "status": "REQUIRES_CONFIRMATION" if reply_id else "SUBMITTED",
            "client_order_id": client_order_id,
            "venue": "IBKR",
            "instrument": intent.instrument,
            "strategy_id": intent.strategy_id,
            "broker_order_id": order_id,
            "reply_id": reply_id,
            "raw": data,
        }

    async def get_order_status(self, broker_order_id):
        if not broker_order_id:
            return {"status": "UNKNOWN"}
        async with httpx.AsyncClient(verify=self.verify_tls, timeout=10) as client:
            r = await client.get(f"{self.base_url}/iserver/account/order/status/{broker_order_id}", headers=self.headers)
            r.raise_for_status()
            data = r.json()
        raw_status = str(data.get("order_status") or data.get("status") or "UNKNOWN").upper().replace(" ", "_")
        status_map = {
            "FILLED": "FILLED", "CANCELLED": "CANCELLED", "CANCELED": "CANCELLED",
            "INACTIVE": "REJECTED", "PRESUBMITTED": "PENDING", "SUBMITTED": "SUBMITTED",
            "PENDINGSUBMIT": "PENDING", "PENDINGCANCEL": "PENDING", "APIPENDING": "PENDING",
        }
        status = status_map.get(raw_status.replace("_", ""), status_map.get(raw_status, raw_status))
        filled = float(data.get("cum_fill") or data.get("filled") or 0)
        avg = float(data.get("avg_price") or data.get("avgPrice") or 0)
        return {"status": status, "broker_order_id": str(broker_order_id), "filled_qty": filled, "avg_price": avg, "raw": data}

    async def cancel_all(self):
        cancelled = []
        async with httpx.AsyncClient(verify=self.verify_tls, timeout=10) as client:
            r = await client.get(f"{self.base_url}/iserver/account/orders", headers=self.headers)
            if not r.is_success:
                return False
            data = r.json()
            rows = data.get("orders", []) if isinstance(data, dict) else []
            for order in rows:
                oid = order.get("orderId") or order.get("order_id")
                if not oid:
                    continue
                cr = await client.delete(f"{self.base_url}/iserver/account/{self.account_id}/order/{oid}", headers=self.headers)
                if cr.is_success:
                    cancelled.append(str(oid))
        return {"cancelled": cancelled}
