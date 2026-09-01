# Final Release Audit — v1.1.0

KCOS is considered a complete **software package** when a clean checkout can reconstruct the declared runtime, expose a simple Genesis/operator GUI, preserve state across restart, enforce deterministic risk independently of strategy/model code, run research outside the six-second decision path, execute only target-position deltas with idempotent order/fill evidence, and report capability truth rather than claiming unverified connectors are live.

## Release gates

- Clean Python package import and test collection
- Full unit/release-contract suite green
- Python bytecode compilation
- JSON/YAML/Compose parsing
- Version/manifest consistency
- Kronos upstream commit pinned consistently
- No runtime vault, `.env.runtime`, private key, or obvious live API token embedded in source
- GUI static assets included in package distribution
- Default GUI bind is loopback-only
- Non-loopback operator APIs require a generated admin token
- Runtime and research are separate 24/7 services
- PostgreSQL and Redis use persistent volumes and restart policies
- Decision heartbeat and maximum state age remain <= 6 seconds
- New risk is rejected on stale state, risk breakers, reconciliation failure, or emergency stop
- Strategy lifecycle cannot skip fixed research/paper/canary evidence gates

## Evidence boundary

A connector adapter being present is **implemented**, not **live-certified**. The capability GUI reports configured/synchronized/external-dependency states. Live certification requires the owner's actual account, entitlements, provider authentication, market sessions, orders/fills and reconciliation evidence.

Docker image construction and real broker/exchange certification require a Docker-capable deployment host and actual provider credentials; they are deployment evidence, not source-code claims.
