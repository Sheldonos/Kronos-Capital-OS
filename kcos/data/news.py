from dataclasses import dataclass
from datetime import datetime, timezone
@dataclass(slots=True)
class NewsEvent: headline:str; source:str; ts:datetime; symbols:list[str]; score:float=0.0; metadata:dict|None=None
class NewsProvider:
    async def stream(self,on_event): raise NotImplementedError
