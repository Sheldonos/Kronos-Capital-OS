import httpx
class AlertManager:
    def __init__(self,webhook=None): self.webhook=webhook
    async def send(self,severity,message,payload=None):
        if not self.webhook:return False
        async with httpx.AsyncClient(timeout=5) as c:
            r=await c.post(self.webhook,json={'severity':severity,'message':message,'payload':payload or {}}); return r.is_success
