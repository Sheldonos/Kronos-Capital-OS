from dataclasses import dataclass
import hashlib
@dataclass(slots=True)
class Hypothesis:
    hypothesis_id:str; subject:str; statement:str; counter_hypothesis:str; priority:float; evidence:dict
class CuriosityEngine:
    def information_value(self,magnitude,economic_relevance,confidence_gap,compute_cost=1.0,research_risk=1.0):
        return float(magnitude)*float(economic_relevance)*float(confidence_gap)/max(.01,float(compute_cost)*float(research_risk))
    def generate(self,instrument,observation):
        out=[]
        for s in observation.get('surprises',[]):
            priority=self.information_value(s.get('magnitude',0),s.get('economic_relevance',.5),s.get('confidence_gap',.5),s.get('compute_cost',1),s.get('research_risk',1))
            statement=s.get('hypothesis') or f'{instrument} behavior has changed under the current regime.'
            counter=s.get('counter') or f'The observed {instrument} change is transient noise with no stable predictive value.'
            hid=hashlib.sha1(f'{instrument}:{statement}'.encode()).hexdigest()[:16]
            out.append(Hypothesis(hid,instrument,statement,counter,priority,s))
        return sorted(out,key=lambda h:h.priority,reverse=True)
