from datetime import datetime,timezone,timedelta
from kcos.config import Settings
from kcos.models import AccountState,OrderIntent
from kcos.risk_kernel import RiskKernel
def fixtures():
    cfg=Settings(_env_file=None)
    acc=AccountState(1000,1000,0,0,0,1000,[])
    intent=OrderIntent("T","PAPER","X","TEST","BUY",1000,100,2,0.9)
    return cfg,acc,intent
def test_clips_size():
    cfg,a,i=fixtures(); d=RiskKernel(cfg).evaluate(i,a,datetime.now(timezone.utc))
    assert d.approved and d.approved_qty<i.qty
def test_stale_blocks():
    cfg,a,i=fixtures(); d=RiskKernel(cfg).evaluate(i,a,datetime.now(timezone.utc)-timedelta(seconds=7))
    assert not d.approved
def test_emergency_blocks():
    cfg,a,i=fixtures(); d=RiskKernel(cfg).evaluate(i,a,datetime.now(timezone.utc),True)
    assert not d.approved
