from __future__ import annotations

import asyncio
import json
import threading
import uuid
from typing import Any

from ..models import AccountState, ConnectorState, MarketEvent, Position


class CoinbaseConnector:
    name = "coinbase"

    def __init__(self, client):
        self.client = client

    async def health(self):
        try:
            await asyncio.to_thread(self.client.get_accounts, limit=1)
            return ConnectorState.CONNECTED
        except Exception:
            return ConnectorState.DEGRADED

    async def account_state(self):
        accounts = await asyncio.to_thread(self.client.get_accounts)
        cash = 0.0
        positions = []
        gross = 0.0
        rows = getattr(accounts, "accounts", []) or []
        for account in rows:
            currency = getattr(account, "currency", "")
            balance = float(getattr(getattr(account, "available_balance", None), "value", 0) or 0)
            if abs(balance) <= 1e-12:
                continue
            if currency in ("USD", "USDC"):
                cash += balance
                continue
            product_id = f"{currency}-USD"
            try:
                product = await asyncio.to_thread(self.client.get_product, product_id)
                price = float(getattr(product, "price", None) or product.get("price", 0))
            except Exception:
                price = 0.0
            if price > 0:
                positions.append(Position("COINBASE", product_id, balance, price, price, 0.0))
                gross += abs(balance * price)
        equity = cash + sum(p.qty * p.mark_price for p in positions)
        return AccountState(equity, cash, gross, 0.0, 0.0, max(equity, 1.0), positions)

    async def place_order(self, intent, approved_qty):
        client_order_id = intent.metadata.get("client_order_id") or f"KCOS-{uuid.uuid4().hex[:20]}"
        if intent.side.upper() == "BUY":
            quote_size = str(float(approved_qty) * float(intent.reference_price))
            raw = await asyncio.to_thread(
                self.client.market_order_buy,
                client_order_id=client_order_id,
                product_id=intent.instrument,
                quote_size=quote_size,
            )
        else:
            raw = await asyncio.to_thread(
                self.client.market_order_sell,
                client_order_id=client_order_id,
                product_id=intent.instrument,
                base_size=str(float(approved_qty)),
            )
        data = raw.to_dict() if hasattr(raw, "to_dict") else (raw if isinstance(raw, dict) else getattr(raw, "__dict__", {}))
        success = bool(data.get("success", True))
        sr = data.get("success_response") or {}
        broker_order_id = sr.get("order_id") or data.get("order_id")
        return {
            "status": "SUBMITTED" if success else "REJECTED",
            "client_order_id": client_order_id,
            "venue": "COINBASE",
            "instrument": intent.instrument,
            "strategy_id": intent.strategy_id,
            "broker_order_id": broker_order_id,
            "raw": data,
        }

    async def get_order_status(self, broker_order_id):
        if not broker_order_id:
            return {"status": "UNKNOWN"}
        raw = await asyncio.to_thread(self.client.get_order, order_id=broker_order_id)
        data = raw.to_dict() if hasattr(raw, "to_dict") else (raw if isinstance(raw, dict) else getattr(raw, "__dict__", {}))
        order = data.get("order") or data
        raw_status = str(order.get("status") or "UNKNOWN").upper()
        status = {"FILLED": "FILLED", "CANCELLED": "CANCELLED", "CANCELED": "CANCELLED", "FAILED": "REJECTED", "EXPIRED": "CANCELLED"}.get(raw_status, "PENDING" if raw_status in {"OPEN", "PENDING", "QUEUED"} else raw_status)
        filled = float(order.get("filled_size") or order.get("filled_value") or 0)
        avg = float(order.get("average_filled_price") or 0)
        return {"status": status, "broker_order_id": str(broker_order_id), "filled_qty": filled, "avg_price": avg, "raw": data}

    async def cancel_all(self):
        try:
            orders = await asyncio.to_thread(self.client.list_orders, order_status=["OPEN", "PENDING"])
            rows = getattr(orders, "orders", []) or []
            ids = [getattr(x, "order_id", None) for x in rows]
            ids = [x for x in ids if x]
            if ids:
                await asyncio.to_thread(self.client.cancel_orders, order_ids=ids)
        except Exception:
            return False
        return True


class CoinbaseMarketDataFeed:
    """Official Coinbase Advanced WebSocket SDK ticker feed."""

    name = "coinbase_market_data"

    def __init__(self, api_key: str | None, api_secret: str | None, product_ids: list[str]):
        self.api_key = api_key
        self.api_secret = api_secret
        self.product_ids = product_ids
        self.stop_event = threading.Event()
        self.connected = False
        self.last_error: str | None = None

    async def health(self):
        return ConnectorState.CONNECTED if self.connected else ConnectorState.RECONNECTING

    async def run(self, on_event):
        loop = asyncio.get_running_loop()

        def blocking():
            from coinbase.websocket import WSClient

            def on_message(message):
                try:
                    obj = json.loads(message) if isinstance(message, str) else message
                    events = obj.get("events", []) if isinstance(obj, dict) else []
                    for event in events:
                        tickers = event.get("tickers", []) if isinstance(event, dict) else []
                        for ticker in tickers:
                            product = ticker.get("product_id")
                            price = ticker.get("price")
                            if product and price:
                                asyncio.run_coroutine_threadsafe(
                                    on_event(MarketEvent("COINBASE", product, "CRYPTO", float(price), metadata={"source": "coinbase_ws"})),
                                    loop,
                                )
                except Exception as exc:
                    self.last_error = repr(exc)

            kwargs: dict[str, Any] = {"on_message": on_message}
            if self.api_key and self.api_secret:
                kwargs.update({"api_key": self.api_key, "api_secret": self.api_secret})
            client = WSClient(**kwargs)
            try:
                client.open()
                client.ticker(product_ids=self.product_ids)
                self.connected = True
                while not self.stop_event.wait(1.0):
                    pass
            finally:
                self.connected = False
                try:
                    client.ticker_unsubscribe(product_ids=self.product_ids)
                    client.close()
                except Exception:
                    pass

        while True:
            try:
                self.stop_event.clear()
                await asyncio.to_thread(blocking)
            except asyncio.CancelledError:
                self.stop_event.set()
                raise
            except Exception as exc:
                self.last_error = repr(exc)
                self.connected = False
                await asyncio.sleep(2)
