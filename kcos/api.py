from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .capabilities import CapabilityResolver
from .config import settings
from .genesis_os import GenesisSupervisor
from .memory import MemoryStore
from .operator_auth import operator_authorized
from .runtime_config import RuntimeConfigStore
from .state import HotState
from .research.strategy_registry import StrategyRegistry


store = RuntimeConfigStore(settings.runtime_dir)
store.apply_to(settings)
state = HotState(settings.redis_url)
memory = MemoryStore(settings.database_url)
registry = StrategyRegistry(settings.database_url)
supervisor = GenesisSupervisor(store)

app = FastAPI(title="Kronos Capital OS", version="1.1.0")
static_dir = Path(__file__).resolve().parent / "web" / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


async def require_operator(
    request: Request,
    x_kcos_admin_token: str | None = Header(default=None, alias="X-KCOS-Admin-Token"),
) -> None:
    host = request.headers.get("host")
    expected = store.generate_admin_token() if settings.require_admin_token_remote else ""
    if not operator_authorized(host, x_kcos_admin_token, expected, settings.require_admin_token_remote):
        raise HTTPException(
            status_code=401,
            detail="KCOS operator token required for non-loopback access. Run `kcos admin-token` on the host.",
            headers={"WWW-Authenticate": "KCOS-Admin-Token"},
        )


@app.get("/")
def index():
    return FileResponse(static_dir / "index.html")


@app.get("/health")
async def health():
    cycle = await state.get_json("runtime:last_cycle", {})
    db_ok = await asyncio.to_thread(memory.health)
    runtime_ok = cycle.get("status") not in {"SLA_BREACH", "INTEGRITY_BLOCKED"}
    return {
        "ok": bool(db_ok and runtime_ok),
        "database": db_ok,
        "instance_id": settings.kcos_instance_id,
        "live_trading_enabled": settings.live_trading_enabled,
        "max_decision_staleness_seconds": settings.max_decision_staleness_seconds,
        "cycle": cycle,
    }


@app.get("/api/bootstrap", dependencies=[Depends(require_operator)])
async def bootstrap():
    desired = await asyncio.to_thread(store.redacted)
    cycle, emergency, actual = await asyncio.gather(
        state.get_json("runtime:last_cycle", {}),
        state.emergency_stop_state(),
        state.get_json("runtime:actual", {"connectors": {}}),
    )
    db_ok = await asyncio.to_thread(memory.health)
    diagnosis = await asyncio.to_thread(supervisor.diagnose, actual)
    return {
        "desired": desired,
        "actual": actual,
        "status": {"cycle": cycle, "emergency_stop": emergency},
        "supervisor": diagnosis,
        "health": {"ok": db_ok and cycle.get("status") not in {"SLA_BREACH", "INTEGRITY_BLOCKED"}, "database": db_ok},
    }


def _validate_desired(desired: dict[str, Any]) -> None:
    owner = desired.get("owner", {})
    autonomy = desired.get("autonomy", {})
    risk = desired.get("risk", {})
    if float(owner.get("initial_capital", 0)) < 0:
        raise HTTPException(422, "initial capital cannot be negative")
    heartbeat = float(autonomy.get("heartbeat_seconds", 6))
    stale = float(autonomy.get("max_decision_staleness_seconds", 6))
    if heartbeat <= 0 or heartbeat > 6 or stale <= 0 or stale > 6:
        raise HTTPException(422, "KCOS decision heartbeat/staleness may not exceed 6 seconds")
    immutable_ceilings = {
        "max_risk_per_trade_pct": 2.0,
        "max_aggregate_open_risk_pct": 10.0,
        "hard_drawdown_stop_pct": 25.0,
        "max_gross_leverage": 3.0,
        "max_venue_exposure_pct": 75.0,
        "max_single_asset_notional_pct": 50.0,
    }
    for key, ceiling in immutable_ceilings.items():
        if key in risk and float(risk[key]) > ceiling:
            raise HTTPException(422, f"{key} exceeds KCOS immutable safety ceiling ({ceiling})")
    connectors = desired.get("connectors", {})
    if autonomy.get("live_trading_enabled") and not any(connectors.get(x, {}).get("enabled") for x in ("ibkr", "coinbase", "oanda")):
        raise HTTPException(422, "live trading requires at least one configured execution venue")


@app.post("/api/setup", dependencies=[Depends(require_operator)])
async def save_setup(payload: dict = Body(...)):
    desired = payload.get("desired") or {}
    secrets = payload.get("secrets") or {}
    _validate_desired(desired)
    redacted = await asyncio.to_thread(store.complete_genesis, desired, secrets)
    await asyncio.to_thread(store.apply_to, settings)
    await state.set_json("config:revision", {"revision": redacted["revision"]})
    await asyncio.to_thread(memory.audit, settings.kcos_instance_id, "desired_state_updated", {"revision": redacted["revision"], "genesis_complete": True})
    return {"ok": True, "desired": redacted, "message": "Saved. Runtime will reconcile desired state automatically."}


@app.get("/api/capabilities", dependencies=[Depends(require_operator)])
async def capabilities():
    actual = await state.get_json("runtime:actual", {"connectors": {}})
    desired = await asyncio.to_thread(store.load)
    return {"items": CapabilityResolver(desired, actual).resolve()}


@app.get("/api/strategies", dependencies=[Depends(require_operator)])
async def strategies():
    try:
        rows = await asyncio.to_thread(registry.list)
        return {"items": [
            {
                "strategy_id": x.strategy_id,
                "version": x.version,
                "stage": x.stage,
                "asset_class": x.asset_class,
                "universe": x.universe,
                "metrics": x.metrics,
                "allocation": x.allocation,
                "enabled": x.enabled,
            } for x in rows
        ]}
    except Exception as exc:
        return {"items": [], "error": repr(exc)}


@app.get("/api/research", dependencies=[Depends(require_operator)])
async def research(limit: int = Query(100, ge=1, le=500)):
    try:
        hypotheses, memories = await asyncio.gather(
            asyncio.to_thread(memory.hypotheses, limit),
            asyncio.to_thread(memory.recent_memories, limit),
        )
        return {"hypotheses": hypotheses, "memories": memories}
    except Exception as exc:
        return {"hypotheses": [], "memories": [], "error": repr(exc)}


@app.get("/api/audit", dependencies=[Depends(require_operator)])
async def audit(limit: int = Query(100, ge=1, le=1000)):
    try:
        return {"items": await asyncio.to_thread(memory.list_audit, limit)}
    except Exception as exc:
        return {"items": [], "error": repr(exc)}


@app.get("/api/status", dependencies=[Depends(require_operator)])
async def status():
    return {
        "cycle": await state.get_json("runtime:last_cycle", {}),
        "actual": await state.get_json("runtime:actual", {}),
        "emergency_stop": await state.emergency_stop_state(),
    }


@app.get("/metrics", dependencies=[Depends(require_operator)])
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/api/emergency-stop", dependencies=[Depends(require_operator)])
@app.post("/emergency-stop", dependencies=[Depends(require_operator)])
async def emergency_stop(reason: str = "owner_request"):
    await state.emergency_stop(True, reason)
    await asyncio.to_thread(memory.audit, settings.kcos_instance_id, "owner_emergency_stop", {"reason": reason})
    return {"ok": True, "emergency_stop": True, "reason": reason}


@app.post("/api/emergency-resume", dependencies=[Depends(require_operator)])
@app.post("/emergency-resume", dependencies=[Depends(require_operator)])
async def emergency_resume():
    await state.emergency_stop(False, "")
    await asyncio.to_thread(memory.audit, settings.kcos_instance_id, "owner_emergency_resume", {})
    return {"ok": True, "emergency_stop": False}
