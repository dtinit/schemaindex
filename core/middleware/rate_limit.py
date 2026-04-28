import logging
import secrets
import time

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 3600
WINDOW_MS = WINDOW_SECONDS * 1000


def get_profile_rate_limit_key(profile):
    return f"api_usage:sliding_log:{profile.id}"


def _get_redis_client():
    try:
        from django_redis import get_redis_connection
    except ImportError:
        return None
    try:
        return get_redis_connection("default")
    except Exception:
        return None


def _check_and_record_valkey(client, key, now_ms, limit):
    """Sorted-set sliding window against Valkey/Redis.

    Sequence:
      1. ZREMRANGEBYSCORE: drop entries older than the window.
      2. ZCARD: count remaining entries.
      3. If under limit: ZADD new entry + PEXPIRE to bound key lifetime.

    Returns (allowed, reason). `reason` is None on success paths and
    "valkey_unavailable" when the Redis call raises.
    """
    import redis

    window_start = now_ms - WINDOW_MS
    # Unique member so concurrent requests at the same ms don't collide on ZADD.
    member = f"{now_ms}:{secrets.token_hex(4)}"

    try:
        pipe = client.pipeline(transaction=False)
        pipe.zremrangebyscore(key, "-inf", window_start)
        pipe.zcard(key)
        _, count = pipe.execute()

        if count >= limit:
            return False, None

        pipe = client.pipeline(transaction=False)
        pipe.zadd(key, {member: now_ms})
        pipe.pexpire(key, WINDOW_MS)
        pipe.execute()
        return True, None
    except redis.exceptions.RedisError as exc:
        logger.warning(
            "rate_limiter_unavailable: failing open (exception=%s)",
            exc.__class__.__name__,
        )
        return True, "valkey_unavailable"


def _check_and_record_locmem(key, now, limit):
    window_start = now - WINDOW_SECONDS
    previous_log = cache.get(key, [])
    last_hour = [ts for ts in previous_log if ts > window_start]
    if len(last_hour) >= limit:
        return False, None
    last_hour.append(now)
    cache.set(key, last_hour, timeout=WINDOW_SECONDS)
    return True, None


def check_and_record_request(profile):
    limit = settings.HOURLY_API_REQUEST_LIMIT
    key = get_profile_rate_limit_key(profile)

    client = _get_redis_client()
    if client is not None:
        now_ms = int(time.time() * 1000)
        return _check_and_record_valkey(client, key, now_ms, limit)

    now = int(time.time())
    return _check_and_record_locmem(key, now, limit)
