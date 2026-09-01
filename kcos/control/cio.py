class AutonomousCIO:
    def propose(self,alpha_scores,portfolio_state):
        return [{'strategy_id':a.strategy_id,'target_weight':a.allocation_weight} for a in alpha_scores if a.score>0]
