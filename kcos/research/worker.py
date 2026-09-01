from __future__ import annotations

import asyncio
import math
from statistics import mean

from ..config import settings
from ..curiosity import CuriosityEngine, Hypothesis
from ..data.market_repository import MarketRepository
from ..memory import MemoryStore
from ..reasoning.provider import ReasoningProvider
from ..runtime_config import RuntimeConfigStore
from ..state import HotState
from ..strategy_factory import StrategyFactory
from .autonomous_lab import AutonomousLab
from .promotion import PromotionEngine
from .strategy_registry import StrategyRegistry


class ResearchWorker:
    """Independent slow path for curiosity, hypothesis generation and strategy validation."""

    def __init__(self):
        self.config = RuntimeConfigStore(settings.runtime_dir)
        self.config.apply_to(settings)
        self.revision = self.config.revision
        self.state = HotState(settings.redis_url)
        self.memory = MemoryStore(settings.database_url)
        self.market = MarketRepository(settings.database_url)
        self.registry = StrategyRegistry(settings.database_url)
        self.curiosity = CuriosityEngine()
        self.factory = StrategyFactory()
        self.lab = AutonomousLab()
        self.promotion = PromotionEngine()
        self.reasoner = ReasoningProvider(settings.llm_api_base, settings.llm_api_key, settings.llm_model)

    def _reload_config(self):
        if self.config.revision == self.revision:
            return
        self.revision = self.config.apply_to(settings)
        self.reasoner = ReasoningProvider(settings.llm_api_base, settings.llm_api_key, settings.llm_model)

    @staticmethod
    def _surprise(prices: list[float]) -> dict | None:
        if len(prices) < 40:
            return None
        recent = prices[-1] / prices[-6] - 1.0
        slow = prices[-1] / prices[-31] - 1.0
        residual = recent - slow / 6.0
        if abs(residual) < 0.005:
            return None
        return {
            "magnitude": min(1.0, abs(residual) * 20),
            "economic_relevance": min(1.0, abs(recent) * 25),
            "confidence_gap": 0.5,
            "hypothesis": "Short-horizon behavior has diverged materially from its medium-horizon baseline under the current state.",
            "counter": "The divergence is transient noise and does not survive realistic costs or out-of-sample testing.",
        }

    async def _reasoned_hypotheses(self, instrument: str, prices: list[float]) -> list[Hypothesis]:
        if not self.reasoner.enabled or len(prices) < 80:
            return []
        returns = [b / a - 1.0 for a, b in zip(prices[-81:-1], prices[-80:]) if a > 0]
        context = {
            "instrument": instrument,
            "observations": len(prices),
            "recent_return_5": prices[-1] / prices[-6] - 1.0,
            "recent_return_30": prices[-1] / prices[-31] - 1.0,
            "recent_volatility": math.sqrt(sum(x * x for x in returns) / max(len(returns), 1)),
            "rule": "Generated ideas remain research-only until deterministic evidence gates pass.",
        }
        rows = await self.reasoner.hypotheses(context, 3)
        out = []
        for row in rows:
            observation = {"surprises": [{
                "magnitude": 0.5,
                "economic_relevance": float(row.get("economic_relevance", 0.5) or 0.5),
                "confidence_gap": float(row.get("confidence_gap", 0.5) or 0.5),
                "hypothesis": str(row.get("statement") or ""),
                "counter": str(row.get("counter_hypothesis") or ""),
            }]}
            out.extend(self.curiosity.generate(instrument, observation))
        return out

    async def discover(self):
        states = await asyncio.to_thread(self.market.latest_states, 5000)
        for state in states:
            instrument = state["instrument"]
            bars = await asyncio.to_thread(self.market.recent_bars, instrument, 512, 60)
            prices = [float(x["close"]) for x in bars]
            surprise = self._surprise(prices)
            hypotheses: list[Hypothesis] = []
            if surprise:
                hypotheses.extend(self.curiosity.generate(instrument, {"surprises": [surprise]}))
            hypotheses.extend(await self._reasoned_hypotheses(instrument, prices))
            for hypothesis in hypotheses[:4]:
                await asyncio.to_thread(
                    self.memory.upsert_hypothesis, hypothesis.hypothesis_id, instrument,
                    hypothesis.statement, hypothesis.counter_hypothesis, hypothesis.priority, hypothesis.evidence,
                )
                for spec in self.factory.variants_from_hypothesis(hypothesis.hypothesis_id, instrument, state["asset_class"]):
                    record = self.factory.record(spec, {"leakage_flags": 0, "oos_observations": 0, "cost_model": True})
                    await asyncio.to_thread(self.registry.upsert, record)

    async def validate(self):
        for strategy in await asyncio.to_thread(self.registry.list, {"RESEARCH", "WALK_FORWARD"}):
            if not strategy.universe:
                continue
            instrument = strategy.universe[0]
            bars = await asyncio.to_thread(self.market.recent_bars, instrument, 1500, 60)
            prices = [float(x["close"]) for x in bars]
            metrics = await asyncio.to_thread(self.lab.evaluate, strategy, prices)
            strategy.metrics.update(metrics)
            next_stage = self.promotion.next_stage(strategy.stage, strategy.metrics)
            if next_stage.value != strategy.stage:
                old = strategy.stage
                strategy.stage = next_stage.value
                await asyncio.to_thread(self.memory.audit, settings.kcos_instance_id, "strategy_promoted", {
                    "strategy_id": strategy.strategy_id, "from": old, "to": strategy.stage,
                    "evidence": {k: strategy.metrics.get(k) for k in ("oos_observations", "oos_sharpe", "max_drawdown", "beats_baselines", "positive_oos_windows")},
                })
            await asyncio.to_thread(self.registry.upsert, strategy)

    async def run_forever(self):
        while True:
            await self.state.set_heartbeat("research")
            try:
                await asyncio.to_thread(self._reload_config)
                await self.discover()
                await self.validate()
                await self.state.set_json("research:last_cycle", {"ok": True, "revision": self.revision})
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                try:
                    await asyncio.to_thread(self.memory.audit, settings.kcos_instance_id, "research_worker_error", {"error": repr(exc)})
                except Exception:
                    pass
                await self.state.set_json("research:last_cycle", {"ok": False, "error": repr(exc), "revision": self.revision})
            await asyncio.sleep(30)


async def run():
    await ResearchWorker().run_forever()
