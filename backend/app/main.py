import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.config import settings
from app.api.v1.router import api_router
from app.api.health import router as health_router
from app.middleware.csrf import CSRFMiddleware
from app.middleware.security import SecurityHeadersMiddleware, RequestLoggingMiddleware
from app.core.rate_limiter import limiter
from app.observability.logging_config import setup_logging, get_logger
from app.observability.metrics import setup_metrics

# Setup structured logging based on environment
setup_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_format=os.getenv("LOG_FORMAT", "json" if settings.is_production else "text"),
)

logger = get_logger(__name__)

app = FastAPI(
    title="Flowrex Backend",
    version=os.getenv("VERSION", "1.0.0"),
    docs_url="/docs" if not settings.is_production else None,  # Disable docs in prod by default
    redoc_url="/redoc" if not settings.is_production else None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Setup Prometheus metrics
setup_metrics(app)

# Middleware stack (order matters - last added runs first)
# 1. Security headers (runs first, adds request ID)
app.add_middleware(SecurityHeadersMiddleware)

# 2. Request logging (uses request ID from security middleware)
if os.getenv("REQUEST_LOGGING_ENABLED", "true").lower() == "true":
    app.add_middleware(RequestLoggingMiddleware)

# 3. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Rate limiting
app.add_middleware(SlowAPIMiddleware)

# 5. CSRF protection (production only)
if settings.is_production:
    app.add_middleware(CSRFMiddleware)

# Include routers
app.include_router(health_router)  # Health check endpoints at root
app.include_router(api_router, prefix="/api/v1")

logger.info(
    "Flowrex backend started",
    extra={
        "environment": os.getenv("ENVIRONMENT", "development"),
        "version": os.getenv("VERSION", "1.0.0"),
    }
)


@app.get("/")
async def root():
    return {"message": "Flowrex API", "docs": "/docs"}

