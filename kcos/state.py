import json
from datetime import datetime, timezone
import redis.asyncio as redis

class HotState:
    def __init__(self, url):
        self.redis = redis.from_url(url, decode_responses=True)
    async def set_json(self, key, value, ttl=None):
        payload = json.dumps(value, default=str)
        if ttl:
            await self.redis.set(key, payload, ex=ttl)
        else:
            await self.redis.set(key, payload)
    async def get_json(self, key, default=None):
        raw = await self.redis.get(key)
        return default if raw is None else json.loads(raw)
    async def set_heartbeat(self, name):
        await self.redis.set(f"heartbeat:{name}", datetime.now(timezone.utc).isoformat(), ex=30)
    async def emergency_stop(self, enabled, reason=""):
        await self.set_json("risk:emergency_stop", {"enabled": enabled, "reason": reason})
    async def emergency_stop_state(self):
        return await self.get_json("risk:emergency_stop", {"enabled": False, "reason": ""})
