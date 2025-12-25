from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import settings

# Central rate limiter used across the app
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url,
    default_limits=["200/minute"],
)
