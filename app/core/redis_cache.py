import redis.asyncio as redis
from datetime import datetime, timezone, date
from typing import Optional, Any
import json
from uuid import UUID
from app.core.config import settings

# --------------------------------------------------------------------------
# CUSTOM JSON ENCODER (Fixes datetime/UUID serialization)
# --------------------------------------------------------------------------
class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)

# --------------------------------------------------------------------------
# REDIS CLIENT INITIALIZATION
# --------------------------------------------------------------------------
try:
    redis_client = redis.Redis.from_url(
        settings.REDIS_URL, 
        decode_responses=True,
        socket_timeout=2,
        socket_connect_timeout=2
    )
except Exception as e:
    print(f"⚠️ Redis initialization failed: {e}")
    redis_client = None

# NGX Trading Hours in UTC (WAT is UTC+1)
NGX_TRADING_START_HOUR = 9
NGX_TRADING_END_HOUR = 13
NGX_TRADING_END_MINUTE = 30

TTL_REALTIME_PRICE = 30          
TTL_OFFHOURS_PRICE = 86400       
TTL_STATIC_DATA = 604800         

def is_ngx_trading_hours() -> bool:
    now_utc = datetime.now(timezone.utc)
    current_hour = now_utc.hour
    current_minute = now_utc.minute
    
    if current_hour < NGX_TRADING_START_HOUR or current_hour > NGX_TRADING_END_HOUR:
        return False
    if current_hour == NGX_TRADING_END_HOUR and current_minute > NGX_TRADING_END_MINUTE:
        return False
    return True

async def get_cached_data(key: str) -> Optional[Any]:
    if not redis_client:
        return None
    try:
        cached = await redis_client.get(key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        print(f"⚠️ Redis GET error for {key}: {e}")
    return None

async def set_cached_data(key: str, data: Any, is_static: bool = False) -> None:
    if not redis_client:
        return
    try:
        # USE THE CUSTOM ENCODER HERE
        serialized_data = json.dumps(data, cls=CustomEncoder)
        ttl = TTL_STATIC_DATA if is_static else (TTL_REALTIME_PRICE if is_ngx_trading_hours() else TTL_OFFHOURS_PRICE)
        await redis_client.setex(key, ttl, serialized_data)
    except Exception as e:
        print(f"⚠️ Redis SETEX error for {key}: {e}")