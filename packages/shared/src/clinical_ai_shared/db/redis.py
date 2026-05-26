from typing import Optional, AsyncGenerator, cast
import redis.asyncio as redis
from tenacity import retry, stop_after_attempt, wait_exponential

from clinical_ai_shared.config import settings
from clinical_ai_shared.observability.logging import get_logger

logger = get_logger(__name__)

_redis_client: Optional[redis.Redis] = None

def get_redis() -> redis.Redis:
    """Get or create the Redis client singleton."""
    global _redis_client
    if _redis_client is None:
        logger.info("creating_redis_client", url=settings.redis_url)
        _redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=lambda retry_state: logger.info(
        "retrying_redis_operation", 
        attempt=retry_state.attempt_number
    ),
)
async def cache_set(key: str, value: str, ttl_seconds: Optional[int] = None) -> bool:
    """Set a value in cache with an optional TTL."""
    client = get_redis()
    try:
        await client.set(key, value, ex=ttl_seconds)
        return True
    except Exception as e:
        logger.error("redis_cache_set_failed", key=key, error=str(e))
        raise

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    before_sleep=lambda retry_state: logger.info(
        "retrying_redis_operation", 
        attempt=retry_state.attempt_number
    ),
)
async def cache_get(key: str) -> Optional[str]:
    """Get a value from cache."""
    client = get_redis()
    try:
        val = await client.get(key)
        return cast(Optional[str], val)
    except Exception as e:
        logger.error("redis_cache_get_failed", key=key, error=str(e))
        raise

async def publish(channel: str, message: str) -> int:
    """Publish a message to a channel."""
    client = get_redis()
    try:
        res = await client.publish(channel, message)
        return cast(int, res)
    except Exception as e:
        logger.error("redis_publish_failed", channel=channel, error=str(e))
        raise

async def subscribe(channel: str) -> AsyncGenerator[str, None]:
    """Subscribe to a channel and yield messages."""
    client = get_redis()
    pubsub = client.pubsub()
    try:
        await pubsub.subscribe(channel)
        async for message in pubsub.listen():
            if message["type"] == "message":
                yield message["data"]
    except Exception as e:
        logger.error("redis_subscribe_failed", channel=channel, error=str(e))
        raise
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()

async def close_redis() -> None:
    """Close the Redis client."""
    global _redis_client
    if _redis_client:
        logger.info("closing_redis_client")
        await _redis_client.close()
        _redis_client = None
        logger.info("redis_client_closed")
