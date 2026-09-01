from kcos.execution.reconciliation import Reconciler
from kcos.models import Position
def test_reconciliation_detects_mismatch():
    a=[Position('X','A',1,10)]; b=[Position('X','A',2,10)]; assert not Reconciler().compare_positions(a,b)['ok']
