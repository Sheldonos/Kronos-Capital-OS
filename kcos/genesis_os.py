from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from .capabilities import CapabilityResolver


@dataclass(slots=True)
class RepairAction:
    subsystem: str
    classification: str
    automatic: bool
    action: str
    reason: str


class GenesisSupervisor:
    """Desired-vs-actual reconciliation and bounded self-repair planner."""

    def __init__(self, config_store):
        self.config_store = config_store

    def diagnose(self, actual: dict[str, Any]) -> dict[str, Any]:
        desired = self.config_store.load()
        capabilities = CapabilityResolver(desired, actual).resolve()
        repairs: list[RepairAction] = []
        for cap in capabilities:
            if cap["status"] == "Partial" and cap["capability_id"].startswith("connector."):
                name = cap["capability_id"].split(".", 1)[1]
                repairs.append(RepairAction(name, "connector_recovery", True, "reconnect_and_resubscribe", cap["detail"]))
            if cap["status"] == "Not covered":
                repairs.append(RepairAction(cap["capability_id"], "owner_dependency", False, cap.get("action") or "owner_action_required", cap["detail"]))
        return {
            "desired_revision": desired.get("revision", 0),
            "genesis_complete": desired.get("genesis_complete", False),
            "capabilities": capabilities,
            "repair_plan": [asdict(r) for r in repairs],
        }

    @staticmethod
    def next_action_for_connector(state: str) -> str:
        return {
            "CONNECTED": "none",
            "SYNCHRONIZED": "none",
            "DEGRADED": "reconnect",
            "STALE": "reconnect_and_replay",
            "RECONNECTING": "wait_with_backoff",
            "REPLAYING": "wait_for_sync",
            "FAILED": "owner_or_configuration_review",
        }.get(state, "probe")
