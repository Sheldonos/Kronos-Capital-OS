import httpx
class SecEdgarClient:
    def __init__(self,user_agent): self.headers={'User-Agent':user_agent,'Accept-Encoding':'gzip, deflate'}
    async def submissions(self,cik):
        cik=str(cik).zfill(10)
        async with httpx.AsyncClient(timeout=15,headers=self.headers) as c:
            r=await c.get(f'https://data.sec.gov/submissions/CIK{cik}.json'); r.raise_for_status(); return r.json()
    async def company_facts(self,cik):
        cik=str(cik).zfill(10)
        async with httpx.AsyncClient(timeout=15,headers=self.headers) as c:
            r=await c.get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json'); r.raise_for_status(); return r.json()
