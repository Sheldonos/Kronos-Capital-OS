class Postmortem:
    def build(self,decision,outcome,attribution):
        return {'decision_id':decision.get('id'),'instrument':decision.get('instrument'),'outcome':outcome,
                'attribution':attribution,'lesson':max(attribution,key=lambda k:abs(attribution[k])) if attribution else 'unknown'}
