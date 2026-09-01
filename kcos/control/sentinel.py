class Sentinel:
    def evaluate(self,latency_s,stale_connectors,reconciliation_ok,queue_depth=0):
        reasons=[]
        if latency_s>6: reasons.append('decision_sla_breach')
        if stale_connectors: reasons.append('stale_connectors:'+','.join(stale_connectors))
        if not reconciliation_ok: reasons.append('reconciliation_mismatch')
        if queue_depth>1000: reasons.append('queue_backlog')
        return {'healthy':not reasons,'reasons':reasons}
