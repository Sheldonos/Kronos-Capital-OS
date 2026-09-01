# Genesis Protocol

Genesis asks only for:
1. jurisdiction/base currency
2. starting deployable capital
3. execution venues
4. market-data credentials
5. macro-data credentials
6. owner hard constraints
7. alert destination
8. whether validated paper/canary strategies may graduate to live automatically

It then creates `.env.runtime` with restrictive permissions, installs the six-second freshness rule,
initializes risk limits, and moves the system into NEWBORN/OBSERVER.

Routine operation should not require owner trade-by-trade participation.
