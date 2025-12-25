"""
Production Health Check Endpoints.

Prompt 18 - Production Deployment.

Provides:
- /health - Basic health check
- /health/ready - Readiness check (dependencies)
- /health/live - Liveness check
"""

from fastapi import APIRouter, Response, status
from sqlalchemy import text
from datetime import datetime, timezone
import os

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Basic health check for load balancers.
    
    Returns 200 if the service is running.
    Used by: NGINX, Docker healthcheck, Kubernetes probes
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "flowrex-backend",
        "version": os.getenv("VERSION", "1.0.0"),
        "environment": os.getenv("ENVIRONMENT", "development"),
    }


@router.get("/health/ready")
async def readiness_check(response: Response):
    """Readiness check with dependency validation.
    
    Checks database and Redis connectivity.
    Returns 503 if any dependency is unavailable.
    Used by: Kubernetes readinessProbe, deployment scripts
    """
    checks = {
        "database": False,
        "redis": False,
    }
    healthy = True
    errors = {}

    # Check database connectivity
    try:
        from app.database import engine
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.fetchone()
        checks["database"] = True
    except Exception as e:
        healthy = False
        errors["database"] = str(e)

    # Check Redis connectivity
    try:
        import redis.asyncio as aioredis
        from app.config import settings
        
        redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        await redis_client.ping()
        await redis_client.close()
        checks["redis"] = True
    except Exception as e:
        healthy = False
        errors["redis"] = str(e)

    # Set response status
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    result = {
        "status": "ready" if healthy else "not_ready",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if errors:
        result["errors"] = errors

    return result


@router.get("/health/live")
async def liveness_check():
    """Liveness check for container orchestration.
    
    Always returns 200 if the process is running.
    Used by: Kubernetes livenessProbe
    """
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/detailed")
async def detailed_health_check(response: Response):
    """Detailed health check with system metrics.
    
    Returns comprehensive health information including:
    - Dependencies status
    - System metrics
    - Application info
    """
    import psutil
    
    checks = {
        "database": False,
        "redis": False,
    }
    healthy = True
    errors = {}

    # Check database
    try:
        from app.database import engine
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.fetchone()
        checks["database"] = True
    except Exception as e:
        healthy = False
        errors["database"] = str(e)

    # Check Redis
    try:
        import redis.asyncio as aioredis
        from app.config import settings
        
        redis_client = aioredis.from_url(settings.redis_url)
        info = await redis_client.info("memory")
        checks["redis"] = True
        checks["redis_memory_mb"] = round(info.get("used_memory", 0) / 1024 / 1024, 2)
        await redis_client.close()
    except Exception as e:
        healthy = False
        errors["redis"] = str(e)

    # System metrics
    system_metrics = {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
    }

    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "healthy" if healthy else "unhealthy",
        "checks": checks,
        "system": system_metrics,
        "errors": errors if errors else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": os.getenv("VERSION", "1.0.0"),
        "environment": os.getenv("ENVIRONMENT", "development"),
    }
