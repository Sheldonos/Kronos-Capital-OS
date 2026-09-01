from __future__ import annotations

import getpass

from .config import settings
from .runtime_config import RuntimeConfigStore


def yn(prompt, default=False):
    value = input(prompt + (" [Y/n] " if default else " [y/N] ")).strip().lower()
    return default if not value else value in {"y", "yes"}


def secret(prompt):
    return getpass.getpass(prompt + ": ").strip()


def main():
    print("\nKRONOS CAPITAL OS — GENESIS v1.1\n")
    print("Tip: the simplest setup is `make launch`, then open http://127.0.0.1:8080.\n")
    store = RuntimeConfigStore(settings.runtime_dir)
    desired = store.load()
    desired["owner"]["jurisdiction"] = input("Owner jurisdiction [US]: ").strip() or "US"
    desired["owner"]["base_currency"] = input("Base currency [USD]: ").strip() or "USD"
    desired["owner"]["initial_capital"] = float(input("Starting deployable capital [1000]: ").strip() or "1000")
    desired["autonomy"]["heartbeat_seconds"] = 6
    desired["autonomy"]["max_decision_staleness_seconds"] = 6
    secrets_payload = {}

    ibkr = yn("Connect Interactive Brokers?")
    desired["connectors"]["ibkr"]["enabled"] = ibkr
    if ibkr:
        desired["connectors"]["ibkr"]["account_id"] = input("IBKR account ID: ").strip()
        desired["connectors"]["ibkr"]["instruments"] = input("IBKR instruments SYMBOL:CONID:ASSETCLASS; … : ").strip()
        secrets_payload["ibkr_bearer_token"] = secret("IBKR bearer/session token (blank if gateway manages auth)")

    cb = yn("Connect Coinbase Advanced Trade?")
    desired["connectors"]["coinbase"]["enabled"] = cb
    if cb:
        desired["connectors"]["coinbase"]["portfolio_id"] = input("Coinbase portfolio ID: ").strip()
        desired["connectors"]["coinbase"]["symbols"] = input("Coinbase products [BTC-USD]: ").strip() or "BTC-USD"
        secrets_payload["coinbase_api_key_name"] = input("Coinbase CDP API key name: ").strip()
        secrets_payload["coinbase_api_private_key"] = secret("Coinbase CDP private key")

    oa = yn("Connect OANDA?")
    desired["connectors"]["oanda"]["enabled"] = oa
    if oa:
        desired["connectors"]["oanda"]["account_id"] = input("OANDA account ID: ").strip()
        desired["connectors"]["oanda"]["symbols"] = input("OANDA symbols [EUR_USD]: ").strip() or "EUR_USD"
        secrets_payload["oanda_access_token"] = secret("OANDA access token")

    db = yn("Connect Databento?", True)
    desired["connectors"]["databento"]["enabled"] = db
    if db:
        desired["connectors"]["databento"]["dataset"] = input("Databento dataset: ").strip()
        desired["connectors"]["databento"]["symbols"] = input("Databento symbols: ").strip()
        secrets_payload["databento_api_key"] = secret("Databento API key")

    fred = yn("Connect FRED macro data?")
    desired["connectors"]["fred"]["enabled"] = fred
    if fred:
        secrets_payload["fred_api_key"] = secret("FRED API key")

    desired["risk"]["max_risk_per_trade_pct"] = float(input("Maximum risk per trade % [0.50]: ").strip() or ".50")
    desired["risk"]["hard_drawdown_stop_pct"] = float(input("Hard portfolio drawdown stop % [10]: ").strip() or "10")
    live = yn("Permit automatic PAPER → CANARY → LIVE graduation only after fixed evidence gates?", False)
    desired["autonomy"]["auto_graduate_to_live"] = live
    desired["autonomy"]["live_trading_enabled"] = live

    result = store.complete_genesis(desired, secrets_payload)
    print(f"\nGENESIS COMPLETE — desired-state revision {result['revision']}")
    print("✓ encrypted credentials\n✓ six-second freshness contract\n✓ deterministic CRO ceilings\n✓ autonomous strategy gates")
    print("\nIf using Docker: make launch, then open http://127.0.0.1:8080")


if __name__ == "__main__":
    main()
