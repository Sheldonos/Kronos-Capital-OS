from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

class AssetClass(str, Enum):
    EQUITY='EQUITY'; ETF='ETF'; FUTURE='FUTURE'; OPTION='OPTION'; FX='FX'; CRYPTO='CRYPTO'; RATE='RATE'; COMMODITY='COMMODITY'; INDEX='INDEX'
class LifecycleState(str, Enum):
    NEWBORN='NEWBORN'; OBSERVER='OBSERVER'; RESEARCHER='RESEARCHER'; PAPER='PAPER'; CANARY='CANARY'; TRADER='TRADER'; PORTFOLIO_MANAGER='PORTFOLIO_MANAGER'; INSTITUTION='INSTITUTION'
class StrategyStage(str, Enum):
    RESEARCH='RESEARCH'; WALK_FORWARD='WALK_FORWARD'; PAPER='PAPER'; CANARY='CANARY'; LIVE='LIVE'; SCALED='SCALED'; RETIRED='RETIRED'

def utcnow(): return datetime.now(timezone.utc)

@dataclass(slots=True)
class Instrument:
    instrument_id:str; symbol:str; venue:str; asset_class:str; currency:str='USD'; contract_multiplier:float=1.0
    tick_size:float=0.01; lot_size:float=1.0; expiry:str|None=None; margin_rate:float|None=None; trading_hours:str|None=None
    settlement:str|None=None; borrow_cost:float|None=None; funding_rate:float|None=None; metadata:dict[str,Any]=field(default_factory=dict)

@dataclass(slots=True)
class Forecast:
    instrument:str; horizon_seconds:int; expected_return:float; direction_probability:float; confidence:float
    volatility:float|None=None; tail_risk:float|None=None; source:str='unknown'; ts:datetime=field(default_factory=utcnow); metadata:dict[str,Any]=field(default_factory=dict)

@dataclass(slots=True)
class RegimeState:
    name:str; confidence:float; volatility_bucket:str; liquidity_bucket:str; trend_bucket:str; ts:datetime=field(default_factory=utcnow); features:dict[str,float]=field(default_factory=dict)

@dataclass(slots=True)
class StrategyRecord:
    strategy_id:str; version:int; stage:str; asset_class:str; universe:list[str]; hypothesis_id:str|None; spec:dict[str,Any]
    metrics:dict[str,Any]=field(default_factory=dict); allocation:float=0.0; enabled:bool=True
