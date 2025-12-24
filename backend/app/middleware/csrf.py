from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import settings


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return await call_next(request)
        if not settings.csrf_protection_enabled:
            return await call_next(request)
        if request.url.path.startswith("/api/v1/auth/login"):
            return await call_next(request)
        if request.url.path.startswith("/api/v1/auth/register"):
            return await call_next(request)
        if not request.headers.get("X-CSRF-Token"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token missing"
            )
        return await call_next(request)
