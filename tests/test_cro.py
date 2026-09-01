from datetime import datetime,timezone,timedelta
from kcos.config import Settings
from kcos.risk_kernel import RiskKernel
from kcos.control.cro import AutonomousCRO
from kcos.models import AccountState,OrderIntent
def test_cro_vetoes_stale_trade():
    cfg=Settings(_env_file=None); cro=AutonomousCRO(RiskKernel(cfg)); a=AccountState(1000,1000,0,0,0,1000,[]); i=OrderIntent('S','PAPER','A','EQ','BUY',1,100,2,.9)
    assert not cro.approve(i,a,datetime.now(timezone.utc)-timedelta(seconds=7)).approved
