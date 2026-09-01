class ResearchDirector:
    def prioritize(self,hypotheses,budget=10): return sorted(hypotheses,key=lambda h:h.priority,reverse=True)[:budget]
