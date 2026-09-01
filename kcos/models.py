from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utcnow():
    return datetime.now(timezone.utc)


class ConnectorState(str, Enum):
    CONNECTED = "CONNECTED"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    RECONNECTING = "RECONNECTING"
    REPLAYING = "REPLAYING"
    SYNCHRONIZED = "SYNCHRONIZED"
    FAILED = "FAILED"


@dataclass(slots=True)
class MarketEvent:
    venue: str
    instrument: str
    asset_class: str
    price: float
    ts: datetime = field(default_factory=utcnow)
    bid: float | None = None
    ask: float | None = None
    volume: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Position:
    venue: str
    instrument: str
    qty: float
    mark_price: float
    avg_price: float = 0.0
    unrealized_pnl: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Signal:
    strategy_id: str
    venue: str
    instrument: str
    asset_class: str
    score: float
    confidence: float
    expected_return: float
    horizon_seconds: int
    ts: datetime = field(default_factory=utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OrderIntent:
    strategy_id: str
    venue: str
    instrument: str
    asset_class: str
    side: str
    qty: float
    reference_price: float
    stop_distance_pct: float
    confidence: float
    reduce_only: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RiskDecision:
    approved: bool
    reason: str
    approved_qty: float = 0.0
    risk_dollars: float = 0.0


@dataclass(slots=True)
class AccountState:
    equity: float
    cash: float
    gross_exposure: float
    daily_pnl: float
    weekly_pnl: float
    peak_equity: float
    positions: list[Position] = field(default_factory=list)
