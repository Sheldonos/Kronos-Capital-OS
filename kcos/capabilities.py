from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class Capability:
    capability_id: str
    name: str
    status: str
    required: bool
    detail: str
    action: str | None = None


class CapabilityResolver:
    """Deterministic capability inventory using Genesis OS status semantics."""

    STATUSES = {"Satisfied", "Partial", "External dependency", "Not covered"}

    def __init__(self, desired_state: dict[str, Any], actual: dict[str, Any] | None = None):
        self.desired = desired_state
        self.actual = actual or {}

    def _connector(self, name: str, required: bool, label: str, purpose: str) -> Capability:
        cfg = self.desired.get("connectors", {}).get(name, {})
        health = self.actual.get("connectors", {}).get(name, {})
        enabled = bool(cfg.get("enabled", False))
        state = str(health.get("state", ""))
        if enabled and state in {"CONNECTED", "SYNCHRONIZED"}:
            return Capability(f"connector.{name}", label, "Satisfied", required, f"Connected — {purpose}")
        if enabled:
            return Capability(f"connector.{name}", label, "Partial", required, f"Configured but not synchronized ({state or 'not checked'})", "Check credentials/session and connection health")
        return Capability(f"connector.{name}", label, "External dependency", required, f"Not configured — {purpose}", f"Connect {label} in Setup")

    def resolve(self) -> list[dict[str, Any]]:
        caps = [
            Capability("core.desired_state", "Authoritative desired state", "Satisfied", True, "Persistent configuration exists outside model/agent memory"),
            Capability("core.secret_boundary", "Encrypted secret boundary", "Satisfied", True, "Local encrypted vault available; external KMS/Vault can replace it"),
            Capability("core.context", "Bounded context compiler", "Satisfied", True, "Hot/warm/institutional memory is retrieved selectively"),
            Capability("core.risk", "Deterministic CRO/risk kernel", "Satisfied", True, "Risk ceilings and stale-state rules are outside the reasoning layer"),
            Capability("core.research", "Autonomous research & promotion", "Satisfied", True, "Hypothesis → evidence → promotion/demotion pipeline present"),
            Capability("core.paper", "Paper execution", "Satisfied", True, "Stateful simulated venue available for validation"),
            self._connector("databento", False, "Databento", "primary institutional live/historical data"),
            self._connector("ibkr", False, "Interactive Brokers", "broad multi-asset execution"),
            self._connector("coinbase", False, "Coinbase Advanced", "crypto execution"),
            self._connector("oanda", False, "OANDA", "dedicated FX execution/data"),
            self._connector("fred", False, "FRED", "macro data"),
            self._connector("sec_edgar", False, "SEC EDGAR", "filings/XBRL fundamentals"),
            self._connector("reasoning", False, "Reasoning endpoint", "optional richer hypothesis generation"),
        ]
        live = bool(self.desired.get("autonomy", {}).get("live_trading_enabled", False))
        execution_configured = any(self.desired.get("connectors", {}).get(x, {}).get("enabled") for x in ("ibkr", "coinbase", "oanda"))
        if live and not execution_configured:
            caps.append(Capability("live.execution", "Live execution path", "Not covered", True, "Live trading is enabled but no execution venue is configured", "Connect at least one live execution venue or disable live trading"))
        elif live:
            configured = [x for x in ("ibkr", "coinbase", "oanda") if self.desired.get("connectors", {}).get(x, {}).get("enabled")]
            certified = {str(x).upper() for x in self.actual.get("certified_live_venues", [])}
            operational = [x for x in configured if str(self.actual.get("connectors", {}).get(x, {}).get("state", "")) in {"CONNECTED", "SYNCHRONIZED"}]
            proven = [x for x in operational if x.upper() in certified]
            if proven and not self.actual.get("integrity_blocked", False):
                caps.append(Capability("live.execution", "Live execution path", "Satisfied", True, f"Authenticated, reconciled and live-fill certified on: {', '.join(proven)}"))
            else:
                caps.append(Capability("live.execution", "Live execution path", "Partial", True, "Configured, but KCOS has not yet observed both current healthy reconciliation and a live fill on an enabled venue", "Complete canary execution and reconciliation"))
        else:
            caps.append(Capability("live.execution", "Live execution path", "External dependency", False, "Intentionally disabled; paper/canary research remains available"))
        return [asdict(c) for c in caps]
