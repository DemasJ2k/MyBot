"""
Security middleware for Flowrex.

Prompt 17 - Deployment Prep.

Provides:
- Security headers (HSTS, X-Content-Type-Options, etc.)
- Request ID injection
- Optional IP-based access controls
"""

import uuid
import os
from typing import Callable, Set, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""

    def __init__(self, app, 
                 enable_hsts: Optional[bool] = None,
                 hsts_max_age: int = 31536000,
                 csp_enabled: Optional[bool] = None,
                 csp_policy: Optional[str] = None):
        super().__init__(app)
        
        # HSTS (only enable in production by default)
        self.enable_hsts = enable_hsts if enable_hsts is not None else (
            os.getenv("ENVIRONMENT", "development") == "production"
        )
        self.hsts_max_age = hsts_max_age
        
        # CSP
        self.csp_enabled = csp_enabled if csp_enabled is not None else (
            os.getenv("CSP_ENABLED", "false").lower() == "true"
        )
        self.csp_policy = csp_policy or os.getenv(
            "CSP_POLICY",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""
        # Generate request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)

        # Add request ID to response
        response.headers["X-Request-ID"] = request_id

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # XSS protection (legacy but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Clickjacking protection
        response.headers["X-Frame-Options"] = "DENY"

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy (formerly Feature-Policy)
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

        # HSTS - only for production over HTTPS
        if self.enable_hsts:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self.hsts_max_age}; includeSubDomains; preload"
            )

        # Content Security Policy
        if self.csp_enabled:
            response.headers["Content-Security-Policy"] = self.csp_policy

        return response


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """Middleware to restrict access based on IP whitelist.
    
    Useful for protecting admin routes or internal endpoints.
    """

    def __init__(self, app, 
                 whitelist: Optional[Set[str]] = None,
                 protected_paths: Optional[Set[str]] = None,
                 enabled: Optional[bool] = None):
        super().__init__(app)
        
        self.enabled = enabled if enabled is not None else (
            os.getenv("IP_WHITELIST_ENABLED", "false").lower() == "true"
        )
        
        # Load whitelist from environment or use provided
        if whitelist:
            self.whitelist = whitelist
        else:
            whitelist_str = os.getenv("IP_WHITELIST", "")
            self.whitelist = set(ip.strip() for ip in whitelist_str.split(",") if ip.strip())
        
        # Paths to protect
        if protected_paths:
            self.protected_paths = protected_paths
        else:
            paths_str = os.getenv("IP_WHITELIST_PATHS", "/admin,/internal")
            self.protected_paths = set(p.strip() for p in paths_str.split(",") if p.strip())

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check IP against whitelist for protected paths."""
        if not self.enabled:
            return await call_next(request)

        # Check if path is protected
        is_protected = any(request.url.path.startswith(p) for p in self.protected_paths)
        
        if is_protected:
            # Get client IP
            client_ip = self._get_client_ip(request)
            
            if client_ip not in self.whitelist:
                return Response(
                    content="Access denied",
                    status_code=403,
                    media_type="text/plain"
                )

        return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request, handling proxies."""
        # Check for proxy headers (in order of trust)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP (original client)
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        
        # Fall back to direct connection IP
        if request.client:
            return request.client.host
        
        return ""


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all requests with context."""

    def __init__(self, app, 
                 log_request_body: bool = False,
                 log_response_body: bool = False,
                 exclude_paths: Optional[Set[str]] = None):
        super().__init__(app)
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.exclude_paths = exclude_paths or {"/health", "/metrics"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response."""
        import time
        import logging
        
        logger = logging.getLogger("flowrex.access")

        # Skip excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)

        # Get request ID (set by SecurityHeadersMiddleware)
        request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())

        # Log request start
        start_time = time.perf_counter()

        # Execute request
        try:
            response = await call_next(request)
            status_code = response.status_code
            error = None
        except Exception as e:
            status_code = 500
            error = str(e)
            raise
        finally:
            # Calculate duration
            duration = time.perf_counter() - start_time

            # Get client IP
            client_ip = request.headers.get("X-Forwarded-For", "")
            if client_ip:
                client_ip = client_ip.split(",")[0].strip()
            elif request.client:
                client_ip = request.client.host
            else:
                client_ip = "unknown"

            # Log entry
            log_data = {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query": str(request.query_params) if request.query_params else None,
                "status_code": status_code,
                "duration_ms": round(duration * 1000, 2),
                "client_ip": client_ip,
                "user_agent": request.headers.get("User-Agent", "")[:100],
            }

            if error:
                log_data["error"] = error

            # Log at appropriate level
            if status_code >= 500:
                logger.error("Request failed", extra=log_data)
            elif status_code >= 400:
                logger.warning("Request client error", extra=log_data)
            else:
                logger.info("Request completed", extra=log_data)

        return response


def setup_security_middleware(app, 
                              enable_security_headers: bool = True,
                              enable_ip_whitelist: bool = False,
                              enable_request_logging: bool = True) -> None:
    """Setup security middleware stack.
    
    Args:
        app: FastAPI application
        enable_security_headers: Add security headers to responses
        enable_ip_whitelist: Enable IP-based access control
        enable_request_logging: Enable request logging
    """
    # Order matters - earlier middleware runs first
    
    if enable_security_headers:
        app.add_middleware(SecurityHeadersMiddleware)
    
    if enable_ip_whitelist:
        app.add_middleware(IPWhitelistMiddleware)
    
    if enable_request_logging:
        app.add_middleware(RequestLoggingMiddleware)
