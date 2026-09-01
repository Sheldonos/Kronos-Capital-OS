from kcos.risk.tail import TailRisk
def test_expected_shortfall_nonnegative_loss_measure():
    x=TailRisk().var_es([-.1,-.05,.01,.02,.03]); assert x['expected_shortfall']>=x['var'] or x['expected_shortfall']>=0
