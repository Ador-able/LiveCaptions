import redis.asyncio as redis

from .config import REDIS_URL

async_redis = redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)

import redis as redis_sync
sync_redis = redis_sync.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
