# Kronos Capital OS — Full Autonomous Quantitative Institution

**Version:** 1.1.0 — final audited release  
**Upstream Kronos:** `shiyu-coder/Kronos`  
**Pinned upstream commit:** `67b630e67f6a18c9e9be918d9b4337c960db1e9a`

Kronos Capital OS (KCOS) is the full package developed across the project chain: a persistent, context-aware, cross-asset autonomous quantitative operating system that can observe markets continuously, maintain institutional memory, map cross-asset relationships, generate hypotheses and strategies, validate them through fixed research gates, allocate capital, pass all trades through an independent deterministic CRO/risk kernel, execute through configured venues, reconcile state, attribute outcomes, detect degradation, and keep learning.

It is **not only Genesis**. Genesis is merely the onboarding/birth sequence.

## System loop

```text
STREAM MARKET + MACRO + FUNDAMENTAL EVENTS
                ↓
        REAL-TIME HOT STATE
                ↓
      SIX-SECOND WORLD SYNC
                ↓
   TREND / REGIME / MARKET GRAPH
                ↓
      CONTEXT + MEMORY RETRIEVAL
                ↓
 KRONOS + FACTOR + VOLATILITY MODELS
                ↓
         ALPHA ENSEMBLE
                ↓
     CURIOSITY / HYPOTHESES
                ↓
     STRATEGY FACTORY + TESTS
                ↓
        ALPHA MARKETPLACE
                ↓
         AUTONOMOUS CIO
                ↓
      PORTFOLIO CONSTRUCTION
                ↓
    INDEPENDENT AUTONOMOUS CRO
                ↓
        DETERMINISTIC RISK
                ↓
        EXECUTION ROUTER
                ↓
      RECONCILIATION / FILLS
                ↓
       P&L ATTRIBUTION / DRIFT
                ↓
     MEMORY + MODEL GOVERNANCE
                ↓
              REPEAT
```

## What is included

### 1. Genesis / owner onboarding + simple GUI
The primary setup path is now a browser-based Genesis Control Center. It captures jurisdiction, deployable capital, broker/exchange credentials, market-data credentials, macro-data credentials, hard risk limits, and whether validated strategies may graduate automatically to live capital. Secrets are encrypted in a persistent local vault and never returned to the browser. A CLI Genesis flow remains available as a fallback.

### 2. Six-second real-time brain
- event-driven feed ingestion
- global heartbeat every 6 seconds or less
- market-state versioning
- connector watchdogs
- stale-state protection
- latency classification
- Prometheus metrics
- emergency-stop API

### 3. Context and institutional memory
- Redis hot state
- in-process hot/warm memory
- PostgreSQL durable institutional memory
- bounded context packets instead of loading full history into a reasoner
- relevant market-graph neighbor retrieval
- decision and audit history

### 4. Cross-asset market map
- rolling return graph
- correlation edges
- lead/lag estimates
- event memory
- multi-horizon trend state
- cross-asset signal component

### 5. Model plane
- pinned upstream Kronos adapter
- asynchronous Kronos inference service
- factor model
- EWMA/realized volatility
- regime classifier
- forecast calibration tracker
- multi-model forecast ensemble

### 6. Curiosity / self-improvement
- surprise detection
- expected-information-value research priority
- hypothesis plus counter-hypothesis generation
- automatic candidate-strategy creation
- persistent experiment/strategy lineage
- model drift controls

### 7. Research integrity and promotion
- leakage guard
- walk-forward split engine
- persistence/momentum/random baselines
- transaction-cost model
- Monte Carlo/bootstrap testing
- generic validation metrics
- strategy registry
- fixed promotion chain:

`RESEARCH → WALK_FORWARD → PAPER → CANARY → LIVE → SCALED`

- automatic demotion/retirement on decay, data-quality failure, execution mismatch, or risk breach

### 8. Alpha marketplace
Strategies compete for capital using risk-adjusted live/OOS performance, expectancy, stability, drawdown, and decay instead of receiving permanent allocation.

### 9. Portfolio construction
- signal-to-order-intent layer
- covariance shrinkage
- risk-adjusted optimizer
- asset-class/venue exposure aggregation
- concentration-based hedge planner
- options intelligence layer with implied volatility, Greeks, term/skew summaries and defined-risk option-expression proposals; live option contracts still require venue-specific contract IDs and validation

### 10. Independent deterministic risk
The AI/research layer cannot override:
- max risk per trade
- aggregate open risk
- daily/weekly loss breakers
- drawdown stop
- gross leverage ceiling
- single-asset notional ceiling
- venue exposure ceiling
- stale-state prohibition
- emergency stop

Tail-risk and stress-test modules are included separately from Kronos forecast uncertainty.

### 11. Cross-asset execution
Execution routing supports asset-class mapping to:
- Interactive Brokers
- Coinbase Advanced Trade
- OANDA
- paper execution

The router can map equities, ETFs, options, futures, rates, commodities and indices to IBKR; FX to OANDA/IBKR; crypto to Coinbase/IBKR where configured and supported by the account.

### 12. Reconciliation and execution quality
- persistent idempotent order manager
- strategy-level position/cost-basis ledger
- target-position execution (trade only the delta, never re-buy merely because the six-second signal is unchanged)
- duplicate-fill protection
- broker/order-status reconciliation
- position reconciliation
- slippage model
- venue health abstraction
- audit events for risk vetoes, orders and execution errors

### 13. Treasury
- deployable-capital calculation
- cash-buffer policy
- venue-cap policy
- **no autonomous withdrawal authority by default**

### 14. Learning layer
- P&L attribution
- postmortems
- drift detector
- model-governor allocation haircut/disable logic
- institutionalized lessons

### 15. 24/7 operations and recovery
- Docker Compose
- PostgreSQL + pgvector
- Redis persistence
- durable market-state/bar recovery after restart
- durable desired-state revisions + encrypted secret vault
- autonomous runtime process
- separate research worker so research cannot consume the six-second live-decision budget
- systemd boot service
- health, status, metrics and emergency-stop endpoints
- loopback-first GUI security plus operator token for non-local access

## Connectors you should provide

Recommended starting configuration:

| System | Purpose |
|---|---|
| Interactive Brokers | Broad multi-asset execution |
| Coinbase Advanced Trade | Crypto execution |
| Databento | Primary live + historical market data |
| FRED | Macro data |
| SEC EDGAR | Public filings/XBRL |
| OANDA | Optional dedicated FX execution/feed |
| PostgreSQL | Durable memory/audit/strategy lineage |
| Redis | Hot state/event cache |
| Vault/KMS/Secrets Manager | Production secret isolation |
| Linux host | Continuous 24/7 operation |

See `docs/CONNECTORS.md` and `docs/24_7_DEPLOYMENT.md`.

## Simple setup

On a Linux host with Docker Engine + Docker Compose:

```bash
make launch
```

Then open **http://127.0.0.1:8080** and complete Genesis in the browser. The Docker build fetches and verifies the pinned upstream Kronos commit automatically; `make bootstrap` is only needed for a local non-Docker development checkout.

The GUI provides Overview, Setup, Capabilities, Strategies, Research and Audit views. KCOS continuously compares desired state with actual connector/runtime state and reports repair actions instead of relying on agent/chat memory.

For a headless/CLI setup instead:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,marketdata,coinbase]"
make genesis
```

After validating the host, enable reboot recovery:

```bash
sudo bash scripts/install_systemd.sh
```

The default Docker port is bound to loopback only. If you intentionally expose the dashboard through a non-loopback hostname or reverse proxy, KCOS requires the operator token printed by:

```bash
kcos admin-token
```

## Safety constitution

The intelligence is allowed to become **smarter, not less constrained**.

Self-improvable under validation:
- strategies
- features
- model/ensemble weights
- market-graph knowledge
- research code
- execution algorithms

Not self-modifiable by the trading/research agents:
- raw credential permissions
- absolute risk ceilings
- validation-gate authority
- audit history
- emergency-stop semantics
- withdrawal/transfer authority

## Reality of the package

KCOS is a complete operating-system architecture with runnable paper-mode infrastructure and live venue adapter boundaries. It does **not** ship with a pre-proven profitable strategy, and no claim is made that Kronos or any dynamically generated strategy has a durable edge. Live strategies only become eligible after the configured evidence gates are satisfied. Provider-specific authentication, KYC, market-data entitlements, instrument identifiers, and account permissions must still be valid.

Automated trading can lose capital. The purpose of the package is to make autonomous research/execution disciplined, observable, recoverable, and bounded by deterministic risk controls.

## Final audit

The release includes `scripts/release_audit.py`, `scripts/build_release.py`, `FILE_HASHES.json`, and `docs/FINAL_AUDIT.md`. `make audit` verifies the declared release contract before packaging.
