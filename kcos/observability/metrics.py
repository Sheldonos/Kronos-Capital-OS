from prometheus_client import Counter,Gauge,Histogram
DECISIONS=Counter('kcos_decisions_total','Decision evaluations')
ORDERS=Counter('kcos_orders_total','Orders submitted',['venue','status'])
CYCLE=Histogram('kcos_cycle_seconds','Global decision cycle latency')
WORLD_VERSION=Gauge('kcos_world_version','Current world state version')
STALE_CONNECTORS=Gauge('kcos_stale_connectors','Number of stale connectors')
