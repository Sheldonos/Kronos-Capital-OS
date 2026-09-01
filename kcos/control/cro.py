class AutonomousCRO:
    """Independent chief-risk authority. The CIO/strategy layer cannot override it."""

    def __init__(self, risk_kernel, stress_engine=None):
        self.risk_kernel = risk_kernel
        self.stress_engine = stress_engine

    def approve(self, intent, account, market_ts, emergency=False, portfolio_risk_dollars=0.0, venue_exposure_dollars=0.0, integrity_blocked=False):
        return self.risk_kernel.evaluate(
            intent,
            account,
            market_ts,
            emergency_stop=emergency,
            aggregate_open_risk_dollars=portfolio_risk_dollars,
            venue_notional_dollars=venue_exposure_dollars,
            integrity_blocked=integrity_blocked,
        )
