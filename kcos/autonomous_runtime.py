from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from .alpha.fusion import AlphaFusion
from .alpha.marketplace import AlphaMarketplace
from .config import settings
from .connectors.factory import parse_ibkr_instruments, register_execution_connectors
from .context_engine import ContextCompiler
from .control.cio import AutonomousCIO
from .control.model_governor import ModelGovernor
from .control.cro import AutonomousCRO
from .control.sentinel import Sentinel
from .data.bar_aggregator import BarAggregator
from .data.bar_store import BarStore
from .data.market_repository import MarketRepository
from .domain import Forecast, StrategyStage
from .execution.order_manager import OrderManager, PENDING_STATUSES
from .execution.paper import PaperVenue
from .execution.position_manager import StrategyPositionManager
from .execution.reconciliation import Reconciler
from .execution.router import ExecutionRouter
from .genesis_os import GenesisSupervisor
from .learning.performance import StrategyPerformanceTracker
from .market_graph import MarketGraph
from .memory import MemoryStore
from .memory_layers import TieredMemory
from .modeling.ensemble import ForecastEnsemble
from .modeling.factors import FactorModel
from .modeling.kronos_service import KronosInferenceService
from .modeling.regime import RegimeModel
from .modeling.volatility import VolatilityModel
from .models import MarketEvent, Position, OrderIntent
from .observability.metrics import CYCLE, DECISIONS, ORDERS, STALE_CONNECTORS, WORLD_VERSION
from .portfolio import PortfolioEngine
from .portfolio_engine.capacity import CapacityModel
from .realtime.watchdog import ConnectorWatchdog
from .research.promotion import PromotionEngine
from .research.strategy_dsl import StrategyDSL
from .research.strategy_registry import StrategyRegistry
from .risk.equity_tracker import EquityTracker
from .risk.stress import StressEngine
from .risk_kernel import RiskKernel
from .runtime_config import RuntimeConfigStore
from .state import HotState
from .trend_engine import TrendEngine


class AutonomousRuntime:
    """Recoverable autonomous trading runtime.

    The six-second loop is intentionally lightweight: live decisions use already-validated
    strategies. Expensive research runs in the independent research worker. Desired state,
    orders, fills, strategy positions, bars and audit evidence persist outside process memory.
    """

    BAR_SECONDS = 60

    def __init__(self):
        self.config_store = RuntimeConfigStore(settings.runtime_dir)
        self.config_revision = self.config_store.apply_to(settings)
        self.supervisor = GenesisSupervisor(self.config_store)

        self.hot = HotState(settings.redis_url)
        self.durable = MemoryStore(settings.database_url)
        self.market_repo = MarketRepository(settings.database_url)
        self.memory = TieredMemory(self.durable)
        self.bars = BarStore()
        self.ohlcv = BarAggregator(self.BAR_SECONDS)
        self.graph = MarketGraph()
        self.context = ContextCompiler(self.memory, self.graph)
        self.trends = TrendEngine()
        self.vol = VolatilityModel()
        self.regimes = RegimeModel()
        self.factors = FactorModel()
        self.ensemble = ForecastEnsemble()
        self.kronos = None

        self.fusion = AlphaFusion()
        self.marketplace = AlphaMarketplace()
        self.dsl = StrategyDSL()
        self.registry = StrategyRegistry(settings.database_url)
        self.promotion = PromotionEngine()
        self.portfolio = PortfolioEngine()
        self.positions = StrategyPositionManager(settings.database_url)
        self.order_manager = OrderManager(settings.database_url)
        self.performance = StrategyPerformanceTracker(settings.database_url)
        self.equity_tracker = EquityTracker(settings.database_url)
        self.risk = RiskKernel(settings)
        self.cio = AutonomousCIO()
        self.model_governor = ModelGovernor()
        self.capacity = CapacityModel()
        self.cro = AutonomousCRO(self.risk, StressEngine())
        self.sentinel = Sentinel()
        self.reconciler = Reconciler()
        self.watchdog = ConnectorWatchdog(settings.max_decision_staleness_seconds)

        self.execution = ExecutionRouter()
        self.paper = PaperVenue(settings.initial_capital)
        self.feed_tasks: dict[str, asyncio.Task] = {}
        self.feed_objects: dict[str, Any] = {}
        self.last_event: dict[str, MarketEvent] = {}
        self.last_completed_close: dict[str, float] = {}
        self.world_version = 0
        self.instrument_locks: dict[str, asyncio.Lock] = {}
        self.account_cache: dict[str, tuple[float, Any]] = {}
        self.allocations: dict[str, float] = {}
        self.strategy_index: dict[str, list[Any]] = {}
        self.strategy_by_id: dict[str, Any] = {}
        self.integrity_blocked = False
        self._emergency_cancelled = False
        self._last_health_probe = 0.0
        self._last_actual: dict[str, Any] = {"connectors": {}}
        self._dirty_market: dict[str, MarketEvent] = {}
        self._closed_bars: list[tuple[MarketEvent, dict]] = []

    # ------------------------------------------------------------------ bootstrap/recovery
    async def initialize(self) -> None:
        await asyncio.to_thread(self._recover_market_state)
        await asyncio.to_thread(self._recover_paper_state)
        await self._configure_connectors(force=True)
        await self._publish_actual(force=True)

    def _recover_market_state(self) -> None:
        try:
            states = self.market_repo.latest_states()
        except Exception as exc:
            self.durable.audit(settings.kcos_instance_id, "market_recovery_failed", {"error": repr(exc)})
            return
        for row in states:
            payload = row.get("payload") or {}
            event = MarketEvent(
                venue=row["venue"], instrument=row["instrument"], asset_class=row["asset_class"],
                price=float(row["price"]), ts=row["ts"], bid=row.get("bid"), ask=row.get("ask"),
                volume=row.get("volume"), metadata=payload.get("metadata", {}),
            )
            self.last_event[event.instrument] = event
            recent = self.market_repo.recent_bars(event.instrument, 512, self.BAR_SECONDS)
            if recent:
                self.ohlcv.seed(event.instrument, recent)
                for bar in recent:
                    self.bars.update(event.instrument, float(bar["close"]), float(bar.get("volume", 0) or 0))
                for prev, cur in zip(recent, recent[1:]):
                    p = float(prev["close"])
                    if p > 0:
                        self.graph.update_return(event.instrument, float(cur["close"]) / p - 1.0, cur["timestamp"])
                self.last_completed_close[event.instrument] = float(recent[-1]["close"])
        if states:
            self.durable.audit(settings.kcos_instance_id, "market_state_recovered", {"instruments": len(states)})

    def _recover_paper_state(self) -> None:
        try:
            aggregate = self.positions.aggregate_positions("PAPER")
            cash = self.durable.paper_cash_from_fills(settings.initial_capital)
            self.paper.restore(aggregate, cash)
            for instrument, event in self.last_event.items():
                self.paper.mark(instrument, event.price)
        except Exception as exc:
            self.durable.audit(settings.kcos_instance_id, "paper_state_recovery_failed", {"error": repr(exc)})

    # ------------------------------------------------------------------ connectors
    async def _configure_connectors(self, force: bool = False) -> None:
        revision = self.config_store.revision
        if not force and revision == self.config_revision:
            return
        self.config_revision = self.config_store.apply_to(settings)
        self.watchdog.max_age = min(float(settings.max_decision_staleness_seconds), 6.0)
        self.risk = RiskKernel(settings)
        self.cro = AutonomousCRO(self.risk, StressEngine())

        for task in self.feed_tasks.values():
            task.cancel()
        if self.feed_tasks:
            await asyncio.gather(*self.feed_tasks.values(), return_exceptions=True)
        self.feed_tasks.clear()
        self.feed_objects.clear()

        router = register_execution_connectors(ExecutionRouter())
        self.paper = self.paper if not force else self.paper
        router.register("PAPER", self.paper)
        self.execution = router
        self.account_cache.clear()

        if settings.kronos_enabled:
            self.kronos = KronosInferenceService(
                settings.kronos_model, settings.kronos_tokenizer, settings.kronos_device,
                min_bars=settings.kronos_min_bars, interval_seconds=settings.kronos_interval_seconds,
            )
        else:
            self.kronos = None

        # OANDA streaming feed uses the same authenticated connector as execution.
        if "OANDA" in self.execution.venues:
            symbols = [x.strip() for x in settings.oanda_symbols.split(",") if x.strip()]
            if symbols:
                self._start_feed("oanda", self.execution.get("OANDA"), self.execution.get("OANDA").run_prices(self.on_market_event, symbols))

        if settings.coinbase_enabled and settings.coinbase_symbols:
            try:
                from .connectors.coinbase import CoinbaseMarketDataFeed
                symbols = [x.strip() for x in settings.coinbase_symbols.split(",") if x.strip()]
                feed = CoinbaseMarketDataFeed(settings.coinbase_api_key_name, settings.coinbase_api_private_key, symbols)
                self._start_feed("coinbase", feed, feed.run(self.on_market_event))
            except Exception as exc:
                self.execution.registration_errors["COINBASE_MARKET_DATA"] = repr(exc)

        if settings.databento_api_key and settings.databento_dataset and settings.databento_symbols:
            try:
                from .connectors.databento_feed import DatabentoFeed
                sub = {
                    "dataset": settings.databento_dataset,
                    "schema": settings.databento_schema,
                    "symbols": [x.strip() for x in settings.databento_symbols.split(",") if x.strip()],
                }
                feed = DatabentoFeed(settings.databento_api_key, sub)
                self._start_feed("databento", feed, feed.run(self.on_market_event))
            except Exception as exc:
                self.execution.registration_errors["DATABENTO"] = repr(exc)

        if settings.ibkr_enabled and settings.ibkr_instruments:
            try:
                from .connectors.ibkr_feed import IbkrSnapshotFeed
                instruments = parse_ibkr_instruments(settings.ibkr_instruments)
                feed = IbkrSnapshotFeed(settings.ibkr_base_url, instruments, settings.ibkr_bearer_token, settings.ibkr_verify_tls)
                self._start_feed("ibkr", feed, feed.run(self.on_market_event))
            except Exception as exc:
                self.execution.registration_errors["IBKR_MARKET_DATA"] = repr(exc)

        self.durable.audit(settings.kcos_instance_id, "runtime_reconfigured", {"revision": revision})

    def _start_feed(self, name: str, feed: Any, coroutine) -> None:
        self.feed_objects[name] = feed
        self.feed_tasks[name] = asyncio.create_task(self._feed_guard(name, coroutine), name=f"kcos-feed-{name}")

    async def _feed_guard(self, name: str, coroutine) -> None:
        try:
            await coroutine
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.durable.audit(settings.kcos_instance_id, "feed_failed", {"feed": name, "error": repr(exc)})

    # ------------------------------------------------------------------ market state
    async def on_market_event(self, event: MarketEvent) -> None:
        now = datetime.now(timezone.utc)
        if event.price <= 0 or event.ts > now.replace(microsecond=now.microsecond) + __import__("datetime").timedelta(seconds=5):
            self.durable.audit(settings.kcos_instance_id, "market_event_rejected", {"instrument": event.instrument, "reason": "invalid_price_or_future_timestamp"})
            return
        self.last_event[event.instrument] = event
        self.world_version += 1
        WORLD_VERSION.set(self.world_version)
        self.paper.mark(event.instrument, event.price)
        self.memory.observe(event.instrument, asdict(event))
        self.graph.update_event(event)
        self.watchdog.seen(event.venue, event.ts)
        self._dirty_market[event.instrument] = event

        current, closed = self.ohlcv.update_with_closed(event)
        if closed:
            self.bars.update(event.instrument, closed["close"], closed.get("volume"))
            prior = self.last_completed_close.get(event.instrument)
            if prior and prior > 0:
                self.graph.update_return(event.instrument, float(closed["close"]) / prior - 1.0, closed["timestamp"])
            self.last_completed_close[event.instrument] = float(closed["close"])
            self._closed_bars.append((event, closed))
            if self.kronos:
                await self.kronos.maybe_schedule(event.instrument, self.ohlcv.bars(event.instrument))

        await self.hot.set_json(
            f"market:{event.instrument}", asdict(event),
            ttl=max(30, int(min(settings.max_decision_staleness_seconds, 6.0) * 5)),
        )

        # Price shocks receive immediate attention, but a per-instrument lock prevents
        # concurrent heartbeat/event evaluations from duplicating target-position work.
        prev_bar = self.last_completed_close.get(event.instrument)
        material = bool(event.metadata.get("material_event"))
        if material or (prev_bar and abs(event.price / prev_bar - 1.0) >= 0.01):
            asyncio.create_task(self.evaluate(event.instrument, "event_trigger", self.allocations))

    async def _persist_market_deltas(self) -> None:
        events = list(self._dirty_market.values())
        bars = list(self._closed_bars)
        self._dirty_market.clear()
        self._closed_bars.clear()
        for event in events:
            await asyncio.to_thread(self.market_repo.upsert_last_event, event)
        for event, bar in bars:
            await asyncio.to_thread(self.market_repo.insert_bar, event.instrument, event.venue, event.asset_class, bar, self.BAR_SECONDS)

    # ------------------------------------------------------------------ models/strategy decisions
    def _base_components(self, instrument: str):
        prices = self.bars.closes(instrument, 400)
        event = self.last_event[instrument]
        if not prices or prices[-1] != event.price:
            prices = prices + [event.price]
        trend = self.trends.summarize(prices)
        vol = self.vol.ewma(prices)
        regime = self.regimes.classify(trend, vol)
        momentum = self.factors.momentum(prices, 20)
        reversal = self.factors.reversal(prices, 10)
        neighbors = self.graph.neighbors(instrument)
        cross = 0.0
        if neighbors:
            weighted = [x["correlation"] * x["last_return"] for x in neighbors.values()]
            cross = sum(weighted) / max(len(weighted), 1)
        components: dict[str, dict[str, float]] = {
            "momentum": {"expected_return": momentum * 0.20, "confidence": min(0.90, 0.50 + abs(momentum) * 5)},
            "reversal": {"expected_return": reversal * 0.10, "confidence": min(0.80, 0.50 + abs(reversal) * 3)},
            "regime": {"expected_return": momentum * 0.10, "confidence": regime.confidence},
            "cross_asset": {"expected_return": cross, "confidence": 0.60 if neighbors else 0.20},
        }
        if self.kronos:
            component = self.kronos.cached_component(instrument)
            if component:
                components["kronos"] = component
        return prices, trend, vol, regime, components

    def _forecast_for_strategy(self, strategy, instrument: str, components: dict[str, dict[str, float]]) -> Forecast:
        compiled = self.dsl.compile(strategy.spec)
        include = self.dsl.component_names(strategy.spec) or None
        forecast = self.ensemble.combine(instrument, 6, components, include=include)
        # Strategy DSL controls eligibility without executing generated code.
        if abs(forecast.expected_return) < compiled.entry_threshold:
            forecast.expected_return = 0.0
            forecast.confidence = min(forecast.confidence, 0.49)
        forecast.metadata.update({"strategy_mode": compiled.mode, "lookback": compiled.lookback})
        return forecast

    def _active_strategies(self, instrument: str):
        return list(self.strategy_index.get(instrument, ()))

    async def _account_state(self, venue_name: str):
        now = time.monotonic()
        cached = self.account_cache.get(venue_name)
        if cached and now - cached[0] < 2.0:
            return cached[1]
        venue = self.execution.get(venue_name)
        account = await asyncio.wait_for(venue.account_state(), timeout=4.0)
        account = await asyncio.to_thread(self.equity_tracker.decorate, venue_name, account)
        self.account_cache[venue_name] = (now, account)
        return account

    def _venue_for_strategy(self, strategy) -> tuple[str, Any, float]:
        if strategy.stage == "PAPER" or not settings.live_trading_enabled:
            return "PAPER", self.execution.get("PAPER"), 1.0
        venue = self.execution.for_asset_class(strategy.asset_class, paper=False)
        # Canary means real capital but deliberately tiny authority.
        multiplier = 0.05 if strategy.stage == "CANARY" else 1.0
        return getattr(venue, "name", "UNKNOWN").upper(), venue, multiplier

    async def _process_fill(self, strategy, fill: dict[str, Any], capital_base: float, stop_distance_pct: float = 2.0, track_performance: bool = True) -> bool:
        fill = dict(fill)
        fill.setdefault("fill_id", uuid.uuid4().hex)
        fill.setdefault("strategy_id", strategy.strategy_id)
        fill.setdefault("venue", "PAPER")
        fill.setdefault("stage", getattr(strategy, "stage", "UNKNOWN"))
        if not await asyncio.to_thread(self.durable.record_fill, fill):
            return False
        await asyncio.to_thread(self.positions.apply_fill, fill, stop_distance_pct, capital_base)
        if not track_performance:
            return True
        marks = {k: v.price for k, v in self.last_event.items()}
        pnl = await asyncio.to_thread(self.positions.strategy_pnl, strategy.strategy_id, marks)
        await asyncio.to_thread(self.performance.snapshot, strategy.strategy_id, strategy.stage, pnl["pnl"], pnl["capital_base"] or capital_base, {"fill_id": fill["fill_id"]})
        live_metrics = await asyncio.to_thread(self.performance.metrics, strategy.strategy_id, strategy.stage)
        strategy.metrics.update(live_metrics)
        strategy.metrics["governance_multiplier"] = self.model_governor.allocation_multiplier(1.0, strategy.metrics.get("decay", 0.0))
        if strategy.stage == "CANARY" and str(fill.get("venue", "")).upper() != "PAPER":
            strategy.metrics["live_authority_ready"] = bool(settings.live_trading_enabled and settings.auto_graduate_to_live)
        if strategy.stage in {"LIVE", "SCALED"}:
            recent_bars = await asyncio.to_thread(self.market_repo.recent_bars, fill.get("instrument"), 1600, self.BAR_SECONDS)
            capacity = self.capacity.estimate(recent_bars, strategy.asset_class)
            strategy.metrics["capacity"] = capacity
            strategy.metrics["capacity_estimated"] = bool(capacity.get("available"))
        # Stage changes are applied only at the synchronized heartbeat boundary in
        # _refresh_allocations. This prevents event-triggered execution from opening a
        # new venue before the previous venue has been flattened.
        await asyncio.to_thread(self.registry.upsert, strategy)
        return True

    async def _execute_strategy(self, strategy, event: MarketEvent, forecast: Forecast, allocation_weight: float, decision_id: str):
        if strategy.metrics.get("transition_pending"):
            return {"status": "SKIPPED_STAGE_TRANSITION"}
        venue_name, venue, stage_multiplier = self._venue_for_strategy(strategy)
        if await asyncio.to_thread(self.order_manager.has_pending, strategy.strategy_id, venue_name, event.instrument):
            return {"status": "SKIPPED_PENDING_ORDER"}
        account = await self._account_state(venue_name)
        current_qty = await asyncio.to_thread(self.positions.current_qty, strategy.strategy_id, venue_name, event.instrument)
        signal = self.fusion.signal(strategy.strategy_id, venue_name, event.instrument, strategy.asset_class, forecast, 1.0, 1.5)
        intent = self.portfolio.intent_from_signal(
            signal, account.equity, event.price, current_qty=current_qty,
            allocation_weight=max(0.0, min(1.0, allocation_weight * stage_multiplier)),
        )
        if not intent:
            return {"status": "NO_REBALANCE"}
        intent.venue = venue_name
        intent.metadata.update(strategy.spec.get("metadata") or {})
        intent.metadata.update(event.metadata or {})

        emergency = (await self.hot.emergency_stop_state()).get("enabled", False)
        portfolio_risk = await asyncio.to_thread(self.positions.risk_used)
        venue_notional = await asyncio.to_thread(self.positions.venue_notional, venue_name)
        risk_decision = self.cro.approve(
            intent, account, event.ts, emergency, portfolio_risk, venue_notional,
            integrity_blocked=(self.integrity_blocked and venue_name != "PAPER"),
        )
        if not risk_decision.approved:
            self.durable.audit(settings.kcos_instance_id, "risk_veto", {
                "strategy_id": strategy.strategy_id, "instrument": event.instrument,
                "venue": venue_name, "reason": risk_decision.reason,
            })
            return {"status": "RISK_VETO", "reason": risk_decision.reason}

        client_id = self.order_manager.client_id(strategy.strategy_id, event.instrument, decision_id)
        intent.metadata["client_order_id"] = client_id
        await asyncio.to_thread(self.order_manager.register_intent, decision_id, intent, risk_decision.approved_qty, client_id)
        try:
            result = await asyncio.wait_for(venue.place_order(intent, risk_decision.approved_qty), timeout=4.0)
        except Exception as exc:
            await asyncio.to_thread(self.order_manager.update, client_id, "ERROR", {"error": repr(exc)})
            raise
        status = str(result.get("status", "SUBMITTED")).upper()
        await asyncio.to_thread(self.order_manager.update, client_id, status, result)
        ORDERS.labels(venue=venue_name, status=status).inc()

        fill = result.get("fill")
        if status.startswith("FILLED") and not fill and venue_name == "PAPER":
            fill = result
        if fill:
            await self._process_fill(strategy, fill, account.equity, intent.stop_distance_pct)
            await asyncio.to_thread(self.order_manager.update, client_id, "FILLED", result)
        if status == "REQUIRES_CONFIRMATION":
            self.durable.audit(settings.kcos_instance_id, "owner_exception_required", {
                "type": "broker_order_warning", "strategy_id": strategy.strategy_id,
                "venue": venue_name, "instrument": event.instrument, "response": result,
            })
        return {"status": status, "client_order_id": client_id, "risk_dollars": risk_decision.risk_dollars}

    async def evaluate(self, instrument: str, reason: str = "heartbeat", allocations: dict[str, float] | None = None):
        lock = self.instrument_locks.setdefault(instrument, asyncio.Lock())
        if lock.locked() and reason == "event_trigger":
            return None
        async with lock:
            event = self.last_event.get(instrument)
            if not event:
                return None
            decision_id = uuid.uuid4().hex
            prices, trend, vol, regime, components = self._base_components(instrument)
            strategies = self._active_strategies(instrument)
            packet = self.context.compile(
                instrument,
                {"world_version": self.world_version, "market": asdict(event), "delta": {}},
                {"managed_positions": await asyncio.to_thread(self.positions.aggregate_positions)},
                {"components": components}, asdict(regime),
            )
            results = []
            for strategy in strategies:
                try:
                    forecast = self._forecast_for_strategy(strategy, instrument, components)
                    result = await self._execute_strategy(strategy, event, forecast, (allocations or {}).get(strategy.strategy_id, 0.0), decision_id)
                    results.append({"strategy_id": strategy.strategy_id, "forecast": asdict(forecast), "result": result})
                except Exception as exc:
                    results.append({"strategy_id": strategy.strategy_id, "error": repr(exc)})
                    self.durable.audit(settings.kcos_instance_id, "execution_error", {"strategy_id": strategy.strategy_id, "instrument": instrument, "error": repr(exc)})
            DECISIONS.inc()
            decision = {
                "reason": reason, "trend": trend, "volatility": vol, "regime": asdict(regime),
                "strategy_results": results,
            }
            await asyncio.to_thread(self.durable.record_decision, decision_id, self.world_version, instrument, packet, decision)
            return {"decision_id": decision_id, **decision}

    # ------------------------------------------------------------------ reconciliation / lifecycle
    async def _refresh_allocations(self) -> None:
        try:
            all_strategies = await asyncio.to_thread(self.registry.list)
            position_snapshot = await asyncio.to_thread(self.positions.snapshot)
            changed: list[tuple[Any, str, str, str]] = []

            for strategy in all_strategies:
                # A venue transition remains blocked until every strategy position on the
                # previous venue is flat. The next heartbeat then releases the new stage.
                if strategy.metrics.get("transition_pending"):
                    try:
                        desired_venue = self._venue_for_strategy(strategy)[0]
                    except Exception:
                        desired_venue = None
                    old_exposure = any(
                        sid == strategy.strategy_id and abs(float(row.get("qty", 0) or 0)) > 1e-12 and str(venue).upper() != str(desired_venue).upper()
                        for (sid, venue, _instrument), row in position_snapshot.items()
                    )
                    if desired_venue and not old_exposure:
                        strategy.metrics.pop("transition_pending", None)
                        strategy.metrics.pop("transition_from", None)
                        strategy.metrics.pop("transition_to", None)
                        changed.append((strategy, strategy.stage, strategy.stage, "transition_complete"))

                action, reason = self.model_governor.strategy_action(strategy.stage, strategy.metrics)
                strategy.metrics["governance_multiplier"] = self.model_governor.allocation_multiplier(1.0, strategy.metrics.get("decay", 0.0))
                old_stage = strategy.stage
                new_stage = old_stage
                change_reason = None

                if action == "DEMOTE" and strategy.stage in {"CANARY", "LIVE", "SCALED"}:
                    new_stage = self.promotion.demote(strategy.stage, "decay").value
                    change_reason = reason
                elif not strategy.metrics.get("transition_pending"):
                    candidate = self.promotion.next_stage(strategy.stage, strategy.metrics).value
                    if candidate != strategy.stage:
                        if candidate == "CANARY" and not settings.live_trading_enabled:
                            strategy.metrics["promotion_blocked"] = "live_trading_disabled"
                        elif candidate == "CANARY":
                            try:
                                self.execution.for_asset_class(strategy.asset_class, paper=False)
                            except Exception:
                                strategy.metrics["promotion_blocked"] = f"no_live_venue_for_{strategy.asset_class}"
                            else:
                                new_stage = candidate
                                change_reason = "evidence_gates_passed"
                                strategy.metrics.pop("promotion_blocked", None)
                        elif candidate in {"LIVE", "SCALED"} and not settings.auto_graduate_to_live:
                            strategy.metrics["promotion_blocked"] = "auto_graduate_to_live_disabled"
                        else:
                            new_stage = candidate
                            change_reason = "evidence_gates_passed"
                            strategy.metrics.pop("promotion_blocked", None)

                if new_stage != old_stage:
                    strategy.stage = new_stage
                    strategy.metrics["last_stage_change_reason"] = change_reason
                    if (old_stage == "PAPER") != (new_stage == "PAPER"):
                        strategy.metrics["transition_pending"] = True
                        strategy.metrics["transition_from"] = old_stage
                        strategy.metrics["transition_to"] = new_stage
                    changed.append((strategy, old_stage, new_stage, change_reason or "governance"))

            # De-duplicate objects that may have both transition cleanup and a stage change.
            unique_changed = {x[0].strategy_id: x for x in changed}
            for strategy, old, new, reason in unique_changed.values():
                await asyncio.to_thread(self.registry.upsert, strategy)
                event_type = "strategy_promoted" if old != new and self.promotion.ORDER.index(StrategyStage(new)) > self.promotion.ORDER.index(StrategyStage(old)) else "strategy_demoted" if old != new else "strategy_transition_complete"
                await asyncio.to_thread(self.durable.audit, settings.kcos_instance_id, event_type, {"strategy_id": strategy.strategy_id, "from": old, "to": new, "reason": reason})

            self.strategy_by_id = {s.strategy_id: s for s in all_strategies}
            active = [s for s in all_strategies if s.stage in {"PAPER", "CANARY", "LIVE", "SCALED"} and s.enabled]
            index: dict[str, list[Any]] = {}
            for strategy in active:
                for instrument in strategy.universe:
                    index.setdefault(instrument, []).append(strategy)
            self.strategy_index = index
            if index:
                await asyncio.to_thread(self.memory.prefetch, list(index), 8)
            ranks = self.marketplace.rank(active)
            proposals = self.cio.propose(ranks, {})
            self.allocations = {x["strategy_id"]: float(x["target_weight"]) for x in proposals}
        except Exception as exc:
            self.allocations = {}
            self.strategy_index = {}
            self.durable.audit(settings.kcos_instance_id, "allocation_refresh_failed", {"error": repr(exc)})

    async def _liquidate_inactive_positions(self) -> None:
        snapshot = await asyncio.to_thread(self.positions.snapshot)
        for (strategy_id, venue_name, instrument), row in snapshot.items():
            qty = float(row.get("qty", 0) or 0)
            if abs(qty) <= 1e-12:
                continue
            strategy = self.strategy_by_id.get(strategy_id)
            desired_venue = None
            if strategy and strategy.enabled and strategy.stage in {"PAPER", "CANARY", "LIVE", "SCALED"}:
                try:
                    desired_venue = self._venue_for_strategy(strategy)[0]
                except Exception:
                    desired_venue = None
            if desired_venue == str(venue_name).upper():
                continue
            event = self.last_event.get(instrument)
            venue_key = str(venue_name).upper()
            if not event or venue_key not in self.execution.venues:
                await asyncio.to_thread(self.durable.audit, settings.kcos_instance_id, "owner_exception_required", {"type": "orphan_position", "strategy_id": strategy_id, "venue": venue_key, "instrument": instrument, "reason": "missing market state or execution connector"})
                continue
            if await asyncio.to_thread(self.order_manager.has_pending, strategy_id, venue_key, instrument):
                continue
            pseudo = strategy or type("RetiredStrategy", (), {"strategy_id": strategy_id, "asset_class": event.asset_class, "spec": {}, "stage": "RETIRED", "version": 0})()
            intent = OrderIntent(
                strategy_id=strategy_id, venue=venue_key, instrument=instrument, asset_class=pseudo.asset_class,
                side="SELL" if qty > 0 else "BUY", qty=abs(qty), reference_price=event.price,
                stop_distance_pct=2.0, confidence=1.0, reduce_only=True,
                metadata={**(getattr(pseudo, "spec", {}).get("metadata") or {}), **(event.metadata or {}), "reason": "strategy_stage_or_venue_exit"},
            )
            account = await self._account_state(venue_key)
            risk_decision = self.cro.approve(intent, account, event.ts, True, 0.0, 0.0, integrity_blocked=True)
            if not risk_decision.approved:
                await asyncio.to_thread(self.durable.audit, settings.kcos_instance_id, "orphan_exit_veto", {"strategy_id": strategy_id, "venue": venue_key, "instrument": instrument, "reason": risk_decision.reason})
                continue
            seed = f"exit:{strategy_id}:{venue_key}:{instrument}:{getattr(pseudo, 'version', 0)}:{getattr(pseudo, 'stage', 'UNKNOWN')}"
            client_id = self.order_manager.client_id(strategy_id, instrument, seed)
            intent.metadata["client_order_id"] = client_id
            await asyncio.to_thread(self.order_manager.register_intent, seed, intent, risk_decision.approved_qty, client_id)
            try:
                result = await asyncio.wait_for(self.execution.get(venue_key).place_order(intent, risk_decision.approved_qty), timeout=4.0)
            except Exception as exc:
                await asyncio.to_thread(self.order_manager.update, client_id, "ERROR", {"error": repr(exc)})
                continue
            status = str(result.get("status", "SUBMITTED")).upper()
            await asyncio.to_thread(self.order_manager.update, client_id, status, result)
            fill = result.get("fill") or (result if status.startswith("FILLED") and venue_key == "PAPER" else None)
            if fill:
                await self._process_fill(pseudo, fill, account.equity, track_performance=False)
                await asyncio.to_thread(self.order_manager.update, client_id, "FILLED", result)
            await asyncio.to_thread(self.durable.audit, settings.kcos_instance_id, "strategy_position_exit_requested", {"strategy_id": strategy_id, "venue": venue_key, "instrument": instrument, "status": status, "desired_venue": desired_venue})

    async def _reconcile_pending_orders(self) -> None:
        for row in await asyncio.to_thread(self.order_manager.list_pending):
            venue_name = str(row["venue"]).upper()
            if venue_name == "PAPER" or venue_name not in self.execution.venues:
                continue
            response = row.get("response") or {}
            broker_id = response.get("broker_order_id") or (response.get("raw") or {}).get("order_id")
            venue = self.execution.get(venue_name)
            if not broker_id or not hasattr(venue, "get_order_status"):
                continue
            try:
                status = await asyncio.wait_for(venue.get_order_status(broker_id), timeout=3.0)
            except Exception as exc:
                self.durable.audit(settings.kcos_instance_id, "order_status_error", {"client_order_id": row["client_order_id"], "error": repr(exc)})
                continue
            normalized = str(status.get("status", "UNKNOWN")).upper()
            await asyncio.to_thread(self.order_manager.update, row["client_order_id"], normalized, status)
            if normalized == "FILLED":
                strategy = await asyncio.to_thread(self.registry.get, row["strategy_id"])
                if not strategy:
                    continue
                qty = float(row.get("approved_qty") or row.get("requested_qty") or 0)
                signed = qty if str(row["side"]).upper() == "BUY" else -qty
                fill = {
                    "fill_id": f"{venue_name}:{broker_id}", "client_order_id": row["client_order_id"],
                    "venue": venue_name, "instrument": row["instrument"], "strategy_id": row["strategy_id"],
                    "side": row["side"], "qty": qty, "signed_qty": signed,
                    "price": float(status.get("avg_price") or self.last_event.get(row["instrument"], MarketEvent(venue_name,row["instrument"],strategy.asset_class,0)).price),
                    "fees": 0.0, "broker_order_id": str(broker_id),
                }
                account = await self._account_state(venue_name)
                await self._process_fill(strategy, fill, account.equity)

    async def _reconcile_positions(self) -> tuple[bool, dict[str, Any]]:
        details: dict[str, Any] = {}
        overall = True
        for name, venue in self.execution.venues.items():
            if name == "PAPER":
                continue
            try:
                account = await self._account_state(name)
                managed_rows = await asyncio.to_thread(self.positions.aggregate_positions, name)
                managed_symbols = {str(r["instrument"]) for r in managed_rows}
                internal = [Position(name, str(r["instrument"]), float(r["qty"]), float(r.get("avg_price") or 0)) for r in managed_rows]
                external = [p for p in account.positions if p.instrument in managed_symbols]
                result = self.reconciler.compare_positions(internal, external)
                details[name] = result
                overall = overall and result["ok"]
                if not result["ok"]:
                    self.durable.audit(settings.kcos_instance_id, "reconciliation_mismatch", {"venue": name, **result})
            except Exception as exc:
                details[name] = {"ok": False, "error": repr(exc)}
                overall = False
        return overall, details

    async def _handle_emergency(self) -> None:
        emergency = await self.hot.emergency_stop_state()
        if emergency.get("enabled") and not self._emergency_cancelled:
            results = await self.execution.cancel_all()
            self._emergency_cancelled = True
            self.durable.audit(settings.kcos_instance_id, "emergency_cancel_all", {"results": results})
        if not emergency.get("enabled"):
            self._emergency_cancelled = False

    async def _publish_actual(self, force: bool = False) -> dict[str, Any]:
        now = time.monotonic()
        if not force and now - self._last_health_probe < 10.0:
            return self._last_actual
        self._last_health_probe = now
        execution_health = await self.execution.health_snapshot()
        connectors: dict[str, Any] = {}
        for name, value in execution_health.items():
            connectors[name.lower()] = value
        for name, feed in self.feed_objects.items():
            try:
                state = await asyncio.wait_for(feed.health(), timeout=2.0)
                connectors[name] = {"state": getattr(state, "value", str(state)), "detail": getattr(feed, "last_error", None)}
            except Exception as exc:
                connectors[name] = {"state": "FAILED", "detail": repr(exc)}
        desired = self.config_store.load()
        # Sources that do not need a persistent socket still report their configured truth.
        if desired["connectors"]["sec_edgar"].get("enabled"):
            connectors["sec_edgar"] = {"state": "CONNECTED", "detail": "public API; validated at request time"}
        if desired["connectors"]["fred"].get("enabled"):
            connectors.setdefault("fred", {"state": "CONNECTED" if settings.fred_api_key else "FAILED", "detail": "API key present" if settings.fred_api_key else "API key missing"})
        if desired["connectors"]["reasoning"].get("enabled"):
            connectors.setdefault("reasoning", {"state": "CONNECTED" if settings.llm_api_base and settings.llm_api_key else "FAILED", "detail": "configured endpoint"})
        certified_live_venues = await asyncio.to_thread(self.durable.live_fill_venues)
        actual = {
            "revision": self.config_revision,
            "connectors": connectors,
            "world_version": self.world_version,
            "instruments": len(self.last_event),
            "managed_positions": len(await asyncio.to_thread(self.positions.aggregate_positions)),
            "pending_orders": len(await asyncio.to_thread(self.order_manager.list_pending)),
            "live_trading_enabled": settings.live_trading_enabled,
            "integrity_blocked": self.integrity_blocked,
            "certified_live_venues": certified_live_venues,
        }
        self._last_actual = actual
        await self.hot.set_json("runtime:actual", actual, ttl=30)
        return actual

    # ------------------------------------------------------------------ six-second global cycle
    async def heartbeat(self):
        started = time.perf_counter()
        await self.hot.set_heartbeat("runtime")
        await self._configure_connectors()
        await self._persist_market_deltas()
        await self._handle_emergency()
        await self._reconcile_pending_orders()
        await self._refresh_allocations()
        pre_reconciliation_ok, pre_reconciliation = await self._reconcile_positions()
        self.integrity_blocked = not pre_reconciliation_ok
        await self._liquidate_inactive_positions()
        actual = await self._publish_actual()

        managed = await asyncio.to_thread(self.positions.aggregate_positions)
        managed_instruments = {str(x["instrument"]) for x in managed if abs(float(x.get("qty", 0) or 0)) > 1e-12}
        instruments = sorted(set(self.strategy_index).union(managed_instruments))
        sem = asyncio.Semaphore(max(1, int(settings.max_concurrent_decisions)))

        async def evaluate_one(symbol: str):
            async with sem:
                return await self.evaluate(symbol, "six_second_heartbeat", self.allocations)

        budget = max(0.25, min(float(settings.heartbeat_seconds), 6.0) - (time.perf_counter() - started))
        if instruments and budget > 0:
            try:
                await asyncio.wait_for(asyncio.gather(*(evaluate_one(x) for x in instruments)), timeout=budget)
            except asyncio.TimeoutError:
                self.durable.audit(settings.kcos_instance_id, "decision_deadline_exceeded", {"instruments": len(instruments)})

        post_reconciliation_ok, reconciliation = await self._reconcile_positions()
        reconciliation_ok = pre_reconciliation_ok and post_reconciliation_ok
        self.integrity_blocked = not post_reconciliation_ok
        reconciliation = {"pre_trade": pre_reconciliation, "post_trade": reconciliation}
        latency = time.perf_counter() - started
        CYCLE.observe(latency)

        # Configured live feeds are the sources whose freshness matters for new risk.
        required = []
        for event in self.last_event.values():
            if event.venue not in required:
                required.append(event.venue)
        stale = self.watchdog.stale(required) if required else []
        STALE_CONNECTORS.set(len(stale))
        sentinel = self.sentinel.evaluate(latency, stale, reconciliation_ok, len(await asyncio.to_thread(self.order_manager.list_pending)))
        status = "HEALTHY"
        if latency > 6.0:
            status = "SLA_BREACH"
        elif not reconciliation_ok:
            status = "INTEGRITY_BLOCKED"
        elif stale:
            status = "DEGRADED"
        elif latency >= 5.0:
            status = "CRITICAL"
        elif latency >= 3.0:
            status = "DEGRADED"
        cycle = {
            "ts": datetime.now(timezone.utc).isoformat(), "latency_seconds": latency,
            "world_version": self.world_version, "status": status, "sentinel": sentinel,
            "reconciliation": reconciliation, "config_revision": self.config_revision,
            "actual": actual,
        }
        await self.hot.set_json("runtime:last_cycle", cycle, ttl=30)
        await asyncio.to_thread(self.durable.audit, settings.kcos_instance_id, "heartbeat", cycle)
        return cycle

    async def run_forever(self):
        loop = asyncio.get_running_loop()
        main_task = asyncio.current_task()

        def _sigterm_handler():
            if main_task and not main_task.done():
                main_task.cancel()

        import signal as _signal
        try:
            loop.add_signal_handler(_signal.SIGTERM, _sigterm_handler)
        except (NotImplementedError, RuntimeError):
            # Windows or environments that do not support add_signal_handler.
            pass

        await self.initialize()
        try:
            while True:
                started = time.monotonic()
                try:
                    await self.heartbeat()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    try:
                        await asyncio.to_thread(self.durable.audit, settings.kcos_instance_id, "runtime_error", {"error": repr(exc)})
                    except Exception:
                        pass
                await asyncio.sleep(max(0.0, min(float(settings.heartbeat_seconds), 6.0) - (time.monotonic() - started)))
        finally:
            for task in self.feed_tasks.values():
                task.cancel()
            await asyncio.gather(*self.feed_tasks.values(), return_exceptions=True)
