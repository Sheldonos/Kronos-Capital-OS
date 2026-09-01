from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone


class ContextCompiler:
    """Compile bounded, relevant context packets rather than whole histories."""

    def __init__(self, memory, graph=None, max_related=8, max_orders=20, max_bytes=48_000):
        self.memory = memory
        self.graph = graph
        self.max_related = max_related
        self.max_orders = max_orders
        self.max_bytes = max_bytes

    def compile(self, instrument, hot_state, portfolio_state, model_state, regime_state, orders=None):
        neighbors = self.graph.neighbors(instrument) if self.graph and hasattr(self.graph, "neighbors") else {}
        ranked = sorted(neighbors.items(), key=lambda kv: abs(float(kv[1].get("correlation", 0))), reverse=True)[:self.max_related]
        mem = self.memory.packet(instrument) if hasattr(self.memory, "packet") else {"institutional": self.memory.recall(instrument, 6)}
        packet = {
            "instrument": instrument,
            "world_version": hot_state.get("world_version"),
            "compiled_at": datetime.now(timezone.utc).isoformat(),
            "market_delta": hot_state.get("delta", {}),
            "market": hot_state.get("market", {}),
            "regime": regime_state,
            "models": model_state,
            "portfolio": portfolio_state,
            "orders": (orders or [])[:self.max_orders],
            "related_markets": dict(ranked),
            "memory": mem,
        }
        raw = json.dumps(packet, default=str, separators=(",", ":"))
        # If bounded retrieval ever exceeds the guardrail, trim ephemeral memory first.
        if len(raw.encode("utf-8")) > self.max_bytes:
            packet["memory"]["warm"] = packet["memory"].get("warm", [])[-4:]
            packet["memory"]["hot"] = packet["memory"].get("hot", [])[-4:]
            packet["related_markets"] = dict(ranked[:4])
        fingerprint = hashlib.sha256(json.dumps(packet, default=str, sort_keys=True).encode()).hexdigest()
        packet["context_hash"] = fingerprint
        return packet
