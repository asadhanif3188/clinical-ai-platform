from typing import Optional, Any
from redis.asyncio import Redis, from_url
from tenacity import retry, stop_after_attempt, wait_exponential
from clinical_ai_shared.config import settings
from clinical_ai_shared.observability.logging import get_logger

logger = get_logger(__name__)

_redis: Optional[Redis] = None

def get_redis() -> Redis:
    global _redis
    if _redis is None:
        logger.info("initializing_redis_client", url=settings.redis.url)
        _redis = from_url(settings.redis.url, decode_responses=True)
    return _redis

async def close_redis() -> None:
    global _redis
    if _redis:
        logger.info("closing_redis_client")
        await _redis.close()
        _redis = None
        logger.info("redis_client_closed")

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
async def cache_set(key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
    logger.info("redis_cache_set", key=key, ttl=ttl_seconds)
    client = get_redis()
    await client.set(key, value, ex=ttl_seconds)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
async def cache_get(key: str) -> Optional[Any]:
    logger.info("redis_cache_get", key=key)
    client = get_redis()
    return await client.get(key)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
async def publish(channel: str, message: str) -> None:
    logger.info("redis_publish", channel=channel)
    client = get_redis()
    await client.publish(channel, message)

async def subscribe(channel: str) -> Any:
    logger.info("redis_subscribe", channel=channel)
    client = get_redis()
    pubsub = client.pubsub()
    await pubsub.subscribe(channel)
    return pubsub
