import httpx
class FredClient:
    def __init__(self,api_key,base='https://api.stlouisfed.org/fred'): self.api_key=api_key; self.base=base.rstrip('/')
    async def series_observations(self,series_id,**params):
        q={'series_id':series_id,'api_key':self.api_key,'file_type':'json',**params}
        async with httpx.AsyncClient(timeout=15) as c:
            r=await c.get(f'{self.base}/series/observations',params=q); r.raise_for_status(); return r.json().get('observations',[])
