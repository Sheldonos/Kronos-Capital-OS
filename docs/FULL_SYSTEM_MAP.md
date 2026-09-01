# Full System Map

This document maps the entire discussed design to source modules.

| Discussed subsystem | Package implementation |
|---|---|
| Birth/Genesis | `kcos/genesis.py` |
| Genesis desired-state supervisor | `kcos/genesis_os.py`, `kcos/runtime_config.py` |
| Simple operator GUI | `kcos/web/static/*`, `kcos/api.py` |
| Operator access boundary | `kcos/operator_auth.py`, `kcos/api.py` |
| Durable market recovery | `kcos/data/market_repository.py`, `kcos/autonomous_runtime.py` |
| Persistent target positions | `kcos/execution/position_manager.py`, `kcos/portfolio.py` |
| Idempotent orders/fills | `kcos/execution/order_manager.py`, `kcos/memory.py` |
| Equity loss-window tracking | `kcos/risk/equity_tracker.py` |
| 6-second global reasoning clock | `kcos/autonomous_runtime.py`, `kcos/realtime/brain.py` |
| Event-driven state | `kcos/state.py`, connector feeds |
| Hot/warm/cold/institutional memory | `kcos/memory_layers.py`, `kcos/memory.py` |
| Context compiler | `kcos/context_engine.py` |
| Instrument abstraction | `kcos/domain.py`, `kcos/data/instruments.py` |
| Multi-horizon trends | `kcos/trend_engine.py` |
| Correlation + lead/lag market graph | `kcos/market_graph.py` |
| Kronos | `kcos/kronos_adapter.py`, `kcos/modeling/kronos_service.py` |
| Volatility | `kcos/modeling/volatility.py` |
| Regime detection | `kcos/modeling/regime.py` |
| Independent factors | `kcos/modeling/factors.py` |
| Forecast ensemble | `kcos/modeling/ensemble.py` |
| Calibration | `kcos/modeling/calibration.py` |
| Curiosity / questions | `kcos/curiosity.py` |
| Hypothesis + counter-hypothesis | `kcos/curiosity.py` |
| Strategy invention | `kcos/strategy_factory.py` |
| Leakage protection | `kcos/research/leakage.py` |
| Baselines | `kcos/research/baselines.py` |
| Walk-forward testing | `kcos/research/walk_forward.py` |
| Cost modeling | `kcos/research/costs.py` |
| Monte Carlo robustness | `kcos/research/monte_carlo.py` |
| Experiment lineage | `kcos/research/experiment.py`, DB schema |
| Strategy registry | `kcos/research/strategy_registry.py` |
| Promotion/demotion | `kcos/research/promotion.py` |
| Alpha fusion | `kcos/alpha/fusion.py` |
| Strategy capital competition | `kcos/alpha/marketplace.py` |
| Autonomous CIO | `kcos/control/cio.py` |
| Autonomous CRO | `kcos/control/cro.py` |
| Research director | `kcos/control/research_director.py` |
| Model governor | `kcos/control/model_governor.py` |
| Sentinel | `kcos/control/sentinel.py` |
| Portfolio optimizer | `kcos/portfolio_engine/optimizer.py` |
| Covariance | `kcos/portfolio_engine/covariance.py` |
| Exposure map | `kcos/portfolio_engine/exposure.py` |
| Hedging | `kcos/portfolio_engine/hedging.py` |
| Options analytics / trade expression | `kcos/derivatives/options.py` |
| Deterministic risk kernel | `kcos/risk_kernel.py` |
| VaR / Expected Shortfall | `kcos/risk/tail.py` |
| Stress tests | `kcos/risk/stress.py` |
| Kill switch | `kcos/risk/kill_switch.py` |
| Execution mapping | `kcos/execution/router.py` |
| Order state | `kcos/execution/order_manager.py` |
| Paper trading | `kcos/execution/paper.py` |
| Reconciliation | `kcos/execution/reconciliation.py` |
| Slippage | `kcos/execution/slippage.py` |
| IBKR | `kcos/connectors/ibkr.py` |
| Coinbase | `kcos/connectors/coinbase.py` |
| OANDA | `kcos/connectors/oanda.py` |
| Databento | `kcos/connectors/databento_feed.py` |
| FRED | `kcos/data/fred.py` |
| SEC EDGAR | `kcos/data/sec_edgar.py` |
| Treasury | `kcos/treasury/manager.py` |
| P&L attribution | `kcos/learning/attribution.py` |
| Drift | `kcos/learning/drift.py` |
| Automated postmortems | `kcos/learning/postmortem.py` |
| Prometheus metrics | `kcos/observability/metrics.py` |
| Alerts | `kcos/observability/alerts.py` |
| Health/emergency API | `kcos/api.py` |
| 24/7 runtime | Docker Compose + systemd scripts |
