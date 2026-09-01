# Strategy Lifecycle

1. **Observation** — anomaly/residual/regime change detected.
2. **Question** — Curiosity Engine scores information value.
3. **Hypothesis + counter-hypothesis** — designed to allow disproof.
4. **Variants** — trend, reversal and cross-asset/regime variants can be produced automatically.
5. **Leakage and provenance checks**.
6. **Baseline comparison** — persistence, momentum and random controls.
7. **Walk-forward OOS**.
8. **Cost/slippage sensitivity**.
9. **Monte Carlo/bootstrap robustness**.
10. **PAPER** only after fixed gates.
11. **CANARY** after sufficient paper observations/days and drawdown limits.
12. **LIVE** after canary evidence.
13. **SCALED** after sufficient live observations, positive net expectancy and capacity checks.
14. **Demotion/retirement** automatically on decay, risk breach, data failure or execution mismatch.

Strategy-generation code is creative. Promotion policy is deterministic.
