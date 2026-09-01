# Connectors

Verified against official provider documentation on 2026-09-01.

## Required for the recommended build

### Interactive Brokers
Broad execution for entitled equities/options/futures/FX and account state.

Genesis inputs:
- account ID
- authentication/session setup
- Web API base URL
- market-data entitlements

KCOS must maintain an authenticated brokerage session for `/iserver` trading functions.
IBKR WebSocket market-data subscriptions require proactive renewal; the runtime watchdog should renew
well before the documented expiration window.

> **TLS WARNING:** The IBKR connector's `verify_tls` parameter defaults to `False` because IBKR's
> Client Portal Web API ships with a self-signed certificate. Operators **must** either:
> 1. Install a trusted CA-signed cert on the IBKR Gateway/TWS host and set `IBKR_VERIFY_TLS=true`
>    in `.env.runtime`, **or**
> 2. Pin the self-signed cert's fingerprint at the network proxy layer and restrict access to
>    the loopback / VPN interface.
>
> Running `verify_tls=False` against an internet-accessible endpoint opens the connection to
> man-in-the-middle attacks. Do not expose the IBKR Gateway to the internet without TLS verification.

Docs:
- https://www.interactivebrokers.com/docs/web-api/authentication/sessions
- https://www.interactivebrokers.com/docs/web-api/v1/ws/market-data/market-data-request
- https://www.interactivebrokers.com/docs/web-api/authentication/oauth-2/introduction

### Coinbase Advanced Trade
Crypto execution.

Genesis inputs:
- CDP API key name
- CDP private key
- portfolio ID

Recommended key permissions:
- view
- trade
- do NOT enable transfer/withdrawal for ordinary trading

Use IP allowlisting.

Docs:
- https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/rest-api
- https://docs.cdp.coinbase.com/api-reference/authentication

### Databento
Preferred streaming/historical market data.

Genesis input:
- DATABENTO_API_KEY

Use streaming subscriptions for the real-time path, plus intraday replay after disconnections.

Docs:
- https://databento.com/docs/api-reference-live
- https://databento.com/docs/getting-started/build-first-app

### FRED
Macro data. Genesis input: FRED_API_KEY.

Docs:
- https://fred.stlouisfed.org/docs/api/fred/v2/api_key.html

### SEC EDGAR
Public submissions/XBRL APIs require no API key. Supply a declared User-Agent.

Docs:
- https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data

## Optional

### OANDA v20
Dedicated FX venue. Inputs: account ID + personal access token.
OANDA pricing stream supports up to four prices/second per instrument and sends heartbeats every 5s.

Docs:
- https://developer.oanda.com/rest-live-v20/authentication/
- https://developer.oanda.com/rest-live-v20/pricing-ep/

## Internal infrastructure connectors

- PostgreSQL: durable memory, audit, strategy/hypothesis lineage
- Redis: hot state, connector health, six-second cycle state
- Vault/KMS/Secrets Manager: production secrets
- alert webhook/email: owner exception notifications

## Treasury
Prefer:
`owner bank → approved funding rail → broker/exchange → trading-only API key`

Do not expose unrestricted bank credentials or withdrawal keys to research/strategy agents.
