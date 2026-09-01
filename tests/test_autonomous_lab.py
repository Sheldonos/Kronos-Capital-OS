from kcos.research.autonomous_lab import AutonomousLab
from kcos.strategy_factory import StrategyFactory
def test_lab_produces_research_metrics():
    f=StrategyFactory(); s=f.record(f.from_hypothesis('H','X','EQUITY',['momentum','regime']))
    prices=[100+i*.1 for i in range(150)]; m=AutonomousLab().evaluate(s,prices); assert m['oos_observations']==100 and m['leakage_flags']==0
