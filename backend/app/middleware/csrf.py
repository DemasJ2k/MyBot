from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import settings


def _get_csrf_cookie(request: Request) -> str | None:
    """Extract CSRF token from cookie."""
    return request.cookies.get("csrftoken")


def _get_csrf_header(request: Request) -> str | None:
    """Extract CSRF token from header."""
    return request.headers.get("X-CSRF-Token")


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
        # Double submit cookie validation
        cookie_token = _get_csrf_cookie(request)
        header_token = _get_csrf_header(request)
        if not cookie_token or not header_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token missing"
            )
        if cookie_token != header_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token invalid"
            )
        return await call_next(request)
