from __future__ import annotations

from ..config import settings
from .ibkr import IbkrConnector
from .oanda import OandaConnector


def parse_ibkr_instruments(value: str):
    out = []
    for chunk in (value or "").split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = [x.strip() for x in chunk.split(":")]
        if len(parts) != 3:
            continue
        symbol, conid, asset_class = parts
        try:
            out.append({"symbol": symbol, "conid": int(conid), "asset_class": asset_class.upper()})
        except ValueError:
            continue
    return out


def register_execution_connectors(router):
    errors = {}
    if settings.ibkr_enabled and settings.ibkr_account_id:
        try:
            router.register("IBKR", IbkrConnector(settings.ibkr_base_url, settings.ibkr_account_id, settings.ibkr_bearer_token, settings.ibkr_verify_tls))
        except Exception as exc:
            errors["IBKR"] = repr(exc)
    if settings.oanda_enabled and settings.oanda_account_id and settings.oanda_access_token:
        try:
            router.register("OANDA", OandaConnector(settings.oanda_base_url, settings.oanda_stream_url, settings.oanda_account_id, settings.oanda_access_token))
        except Exception as exc:
            errors["OANDA"] = repr(exc)
    if settings.coinbase_enabled and settings.coinbase_api_key_name and settings.coinbase_api_private_key:
        try:
            from coinbase.rest import RESTClient
            from .coinbase import CoinbaseConnector
            client = RESTClient(api_key=settings.coinbase_api_key_name, api_secret=settings.coinbase_api_private_key, timeout=5)
            router.register("COINBASE", CoinbaseConnector(client))
        except Exception as exc:
            errors["COINBASE"] = repr(exc)

    for asset in ("EQUITY", "ETF", "OPTION", "FUTURE", "RATE", "COMMODITY", "INDEX"):
        if "IBKR" in router.venues:
            router.map_asset_class(asset, "IBKR")
    if "OANDA" in router.venues:
        router.map_asset_class("FX", "OANDA")
    elif "IBKR" in router.venues:
        router.map_asset_class("FX", "IBKR")
    if "COINBASE" in router.venues:
        router.map_asset_class("CRYPTO", "COINBASE")
    elif "IBKR" in router.venues:
        router.map_asset_class("CRYPTO", "IBKR")
    router.registration_errors = errors
    return router
