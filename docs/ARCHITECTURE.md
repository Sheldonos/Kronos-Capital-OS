# Architecture

Planes:
1. Control
2. Market Data
3. Market Graph
4. Context/Memory
5. Models
6. Trend/Regime
7. Strategy Factory
8. Alpha Marketplace
9. Portfolio
10. Deterministic Risk
11. Execution/Reconciliation
12. Learning
13. Observability

## Context discipline
Reasoners never receive the entire database. A decision packet contains only:
- affected instruments
- open positions/orders
- deltas since previous world state
- relevant multi-horizon trend/regime state
- model outputs
- retrieved memories related to the current subject/regime
- portfolio/risk state

## Self-improvement
The system may evolve strategies, features, ensembles, market graph edges, research code, and
execution algorithms under validation.

It may not self-modify credential permissions, absolute risk ceilings, emergency-stop semantics,
audit history, or validation-gate authority.
