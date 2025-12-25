from datetime import datetime, timezone
from typing import Optional
from jose import JWTError
from redis.asyncio import Redis

from app.config import settings
from app.auth.jwt import decode_token

redis_client = Redis.from_url(settings.redis_url, decode_responses=True)

BLACKLIST_PREFIX = "token:blacklist:"


def _token_ttl(exp: int) -> int:
    now_ts = int(datetime.now(timezone.utc).timestamp())
    ttl = exp - now_ts
    return max(ttl, 0)


async def blacklist_token(token: str) -> None:
    try:
        payload = decode_token(token)
    except JWTError:
        return
    exp = payload.get("exp")
    jti = payload.get("jti")
    if not exp or not jti:
        return
    ttl = _token_ttl(int(exp))
    if ttl <= 0:
        return
    await redis_client.setex(f"{BLACKLIST_PREFIX}{jti}", ttl, "1")


async def is_token_blacklisted(token: str) -> bool:
    try:
        payload = decode_token(token)
    except JWTError:
        return False
    jti = payload.get("jti")
    if not jti:
        return False
    return bool(await redis_client.get(f"{BLACKLIST_PREFIX}{jti}"))


async def is_jti_blacklisted(jti: str) -> bool:
    return bool(await redis_client.get(f"{BLACKLIST_PREFIX}{jti}"))
