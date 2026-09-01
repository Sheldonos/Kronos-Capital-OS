from dataclasses import dataclass,asdict
from datetime import datetime,timezone
import hashlib
@dataclass(slots=True)
class Experiment: experiment_id:str; hypothesis_id:str; strategy_id:str; dataset_hash:str; parameters:dict; status:str='CREATED'; results:dict|None=None
class ExperimentManager:
    def create(self,hypothesis_id,strategy_id,dataset_bytes,parameters):
        h=hashlib.sha256(dataset_bytes).hexdigest(); eid='EXP-'+hashlib.sha1(f'{hypothesis_id}:{strategy_id}:{h}:{parameters}'.encode()).hexdigest()[:14].upper()
        return Experiment(eid,hypothesis_id,strategy_id,h,parameters)
