# 17_DEPLOYMENT_PREP.md

## Purpose and Scope

This prompt instructs Opus 4.5 to prepare the Flowrex trading platform for production deployment by implementing comprehensive deployment readiness procedures, environment management, secrets handling, and pre-deployment validation gates.

**Core Principles:**
1. **Reproducibility**: Deployments must be 100% reproducible across environments
2. **Reversibility**: All deployments must be reversible via automated rollback
3. **Security First**: Secrets never committed to version control
4. **Environment Parity**: Dev/staging/prod environments must be nearly identical
5. **Deployment Gates**: Automated gates prevent broken code from reaching production
6. **Observability**: Comprehensive logging, metrics, and alerting from day one

**Integration Points:**
- Builds on TESTING_AND_VALIDATION.md (prompt 15) for test gates
- Extends BACKEND_CORE.md (prompt 02) with production configurations
- Integrates with all components for environment-aware behavior

---

## Environment Separation

### Three Environments

**1. Development (dev)**
- Local development on developer machines
- Docker Compose for local services
- Simulated broker adapter only
- SQLite or local PostgreSQL
- Hot reload enabled
- Debug logging enabled
- No rate limiting
- Mock external services

**2. Staging (staging)**
- Production-like environment for testing
- Deployed to cloud infrastructure
- Real PostgreSQL database (separate instance)
- Real Redis instance
- Can use paper trading broker adapters
- Production-level logging
- Rate limiting enabled
- Real external services (TwelveData sandbox if available)

**3. Production (prod)**
- Live environment serving real users
- Full redundancy and scaling
- Production PostgreSQL with replicas
- Production Redis with persistence
- Real broker connections (OANDA, MT5)
- Strict rate limiting
- Minimal logging (no sensitive data)
- Maximum security hardening

### Environment Configuration File

**File: `.env.example`**

```bash
# ============================================
# FLOWREX ENVIRONMENT CONFIGURATION
# ============================================
# Copy this file to .env and fill in values
# NEVER commit .env to version control

# --- ENVIRONMENT ---
NODE_ENV=development  # development | staging | production
ENVIRONMENT=dev       # dev | staging | prod

# --- APPLICATION ---
APP_NAME=Flowrex
APP_VERSION=1.0.0
APP_URL=http://localhost:3000
API_URL=http://localhost:8000

# --- BACKEND ---
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
BACKEND_WORKERS=4
BACKEND_RELOAD=true  # Only true in development
LOG_LEVEL=INFO       # DEBUG | INFO | WARNING | ERROR | CRITICAL

# --- DATABASE ---
DATABASE_URL=postgresql+asyncpg://flowrex:password@localhost:5432/flowrex_dev
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=3600

# --- REDIS ---
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=50

# --- JWT AUTHENTICATION ---
JWT_SECRET_KEY=your-super-secret-jwt-key-min-32-chars-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# --- CORS ---
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
CORS_ALLOW_CREDENTIALS=true

# --- DATA PROVIDERS ---
TWELVEDATA_API_KEY=your-twelvedata-api-key-here
TWELVEDATA_BASE_URL=https://api.twelvedata.com

# --- BROKERS ---
# OANDA
OANDA_ACCOUNT_ID=
OANDA_API_KEY=
OANDA_BASE_URL=https://api-fxpractice.oanda.com  # Paper trading
# OANDA_BASE_URL=https://api-fxtrade.oanda.com   # Live trading

# MT5
MT5_LOGIN=
MT5_PASSWORD=
MT5_SERVER=

# --- RATE LIMITING ---
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST=10

# --- WEBSOCKET ---
WS_HEARTBEAT_INTERVAL=30
WS_MAX_CONNECTIONS=100
WS_MESSAGE_QUEUE_SIZE=1000

# --- SECURITY ---
SECURITY_HEADERS_ENABLED=true
CSRF_PROTECTION_ENABLED=true
SESSION_COOKIE_SECURE=false  # true in production
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=lax  # strict in production

# --- MONITORING ---
SENTRY_DSN=
SENTRY_ENVIRONMENT=development
SENTRY_TRACES_SAMPLE_RATE=0.1

# --- LOGGING ---
LOG_FORMAT=json  # json | text
LOG_FILE_ENABLED=false
LOG_FILE_PATH=/var/log/flowrex/app.log
LOG_FILE_MAX_BYTES=10485760  # 10MB
LOG_FILE_BACKUP_COUNT=5

# --- PROMETHEUS METRICS ---
METRICS_ENABLED=true
METRICS_PORT=9090

# --- BACKUP ---
BACKUP_ENABLED=true
BACKUP_SCHEDULE=0 2 * * *  # 2 AM daily
BACKUP_RETENTION_DAYS=30
BACKUP_S3_BUCKET=
BACKUP_S3_REGION=us-east-1

# --- FEATURE FLAGS ---
FEATURE_AI_AGENTS_ENABLED=true
FEATURE_BACKTESTING_ENABLED=true
FEATURE_OPTIMIZATION_ENABLED=true
FEATURE_LIVE_TRADING_ENABLED=false  # true only when ready

# --- SMTP (for email notifications) ---
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=noreply@flowrex.app
SMTP_USE_TLS=true

# --- FRONTEND BUILD ---
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
NEXT_PUBLIC_ENVIRONMENT=development
```

---

## Secrets Management

### Secrets Management Strategy

**File: `backend/app/config/secrets.py`**

```python
import os
from typing import Optional
from functools import lru_cache


class SecretsManager:
    """Centralized secrets management."""

    def __init__(self, environment: str = "development"):
        self.environment = environment
        self._cache = {}

    def get_secret(self, key: str, default: Optional[str] = None) -> str:
        """Get secret from environment or secrets manager."""
        # In development, read from .env
        if self.environment == "development":
            return os.getenv(key, default)

        # In staging/production, read from secrets manager
        # This example uses environment variables but should be replaced
        # with AWS Secrets Manager, HashiCorp Vault, or similar
        return self._get_from_secrets_manager(key, default)

    def _get_from_secrets_manager(self, key: str, default: Optional[str] = None) -> str:
        """Get secret from external secrets manager."""
        # Check cache first
        if key in self._cache:
            return self._cache[key]

        # Example: AWS Secrets Manager integration
        # Uncomment and configure for production use
        # import boto3
        # from botocore.exceptions import ClientError
        #
        # session = boto3.session.Session()
        # client = session.client(
        #     service_name='secretsmanager',
        #     region_name=os.getenv('AWS_REGION', 'us-east-1')
        # )
        #
        # try:
        #     response = client.get_secret_value(SecretId=f"flowrex/{self.environment}/{key}")
        #     secret = response['SecretString']
        #     self._cache[key] = secret
        #     return secret
        # except ClientError:
        #     return default

        # Fallback to environment variable
        return os.getenv(key, default)

    def validate_required_secrets(self) -> tuple[bool, list[str]]:
        """Validate that all required secrets are present."""
        required_secrets = [
            "JWT_SECRET_KEY",
            "DATABASE_URL",
            "REDIS_URL",
            "TWELVEDATA_API_KEY",
        ]

        # Additional secrets required in production
        if self.environment == "production":
            required_secrets.extend([
                "SENTRY_DSN",
                "BACKUP_S3_BUCKET",
                "SMTP_PASSWORD",
            ])

        missing = []
        for secret in required_secrets:
            value = self.get_secret(secret)
            if not value:
                missing.append(secret)

        return len(missing) == 0, missing


@lru_cache()
def get_secrets_manager() -> SecretsManager:
    """Get cached secrets manager instance."""
    environment = os.getenv("ENVIRONMENT", "development")
    return SecretsManager(environment)
```

**File: `backend/app/config/settings.py`** (update)

```python
from pydantic_settings import BaseSettings
from app.config.secrets import get_secrets_manager


class Settings(BaseSettings):
    """Application settings loaded from environment and secrets."""

    # Application
    app_name: str = "Flowrex"
    environment: str = "development"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    reload: bool = False

    # Database
    database_url: str
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # Redis
    redis_url: str

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # Data Providers
    twelvedata_api_key: str

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 60

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Metrics
    metrics_enabled: bool = True
    metrics_port: int = 9090

    # Feature Flags
    feature_live_trading_enabled: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = False

    @classmethod
    def load(cls) -> "Settings":
        """Load settings from environment and secrets manager."""
        secrets_manager = get_secrets_manager()

        # Validate required secrets
        valid, missing = secrets_manager.validate_required_secrets()
        if not valid:
            raise ValueError(f"Missing required secrets: {missing}")

        # Load settings with secrets
        return cls(
            database_url=secrets_manager.get_secret("DATABASE_URL"),
            redis_url=secrets_manager.get_secret("REDIS_URL"),
            jwt_secret_key=secrets_manager.get_secret("JWT_SECRET_KEY"),
            twelvedata_api_key=secrets_manager.get_secret("TWELVEDATA_API_KEY"),
        )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings.load()
```

---

## Database Migration Process

### Migration Strategy

**File: `backend/scripts/migrate.py`**

```python
#!/usr/bin/env python3
"""Database migration script with safety checks."""

import asyncio
import sys
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine
from app.config.settings import get_settings


async def check_database_connection() -> bool:
    """Verify database is accessible."""
    settings = get_settings()
    try:
        engine = create_async_engine(settings.database_url)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        print("✓ Database connection successful")
        return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False


async def create_backup(backup_name: str) -> bool:
    """Create database backup before migration."""
    settings = get_settings()

    # Only backup in staging/production
    if settings.environment == "development":
        print("⊙ Skipping backup in development environment")
        return True

    print(f"Creating backup: {backup_name}")

    # Example: PostgreSQL backup using pg_dump
    # This should be replaced with your actual backup strategy
    import subprocess

    try:
        # Parse database URL
        # postgresql+asyncpg://user:pass@host:port/dbname
        db_url = settings.database_url.replace("postgresql+asyncpg://", "")
        parts = db_url.split("@")
        credentials = parts[0]
        location = parts[1]

        user = credentials.split(":")[0]
        host_port_db = location.split("/")
        host_port = host_port_db[0].split(":")
        host = host_port[0]
        port = host_port[1] if len(host_port) > 1 else "5432"
        dbname = host_port_db[1]

        backup_file = f"/tmp/{backup_name}.sql"

        subprocess.run(
            [
                "pg_dump",
                f"-h{host}",
                f"-p{port}",
                f"-U{user}",
                f"-F",
                "p",
                f"-f{backup_file}",
                dbname,
            ],
            check=True,
            capture_output=True,
        )

        print(f"✓ Backup created: {backup_file}")
        return True

    except Exception as e:
        print(f"✗ Backup failed: {e}")
        return False


def run_migrations() -> bool:
    """Run Alembic migrations."""
    try:
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        print("✓ Migrations completed successfully")
        return True
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        return False


async def verify_migration() -> bool:
    """Verify migration was successful."""
    settings = get_settings()
    try:
        engine = create_async_engine(settings.database_url)
        async with engine.connect() as conn:
            # Check that key tables exist
            result = await conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('users', 'strategies', 'signals', 'trades')
            """))
            tables = [row[0] for row in result]

            required_tables = ['users', 'strategies', 'signals', 'trades']
            missing = set(required_tables) - set(tables)

            if missing:
                print(f"✗ Missing tables: {missing}")
                return False

        await engine.dispose()
        print("✓ Migration verification successful")
        return True

    except Exception as e:
        print(f"✗ Migration verification failed: {e}")
        return False


async def main():
    """Main migration workflow."""
    print("=" * 60)
    print("DATABASE MIGRATION")
    print("=" * 60)

    settings = get_settings()
    print(f"Environment: {settings.environment}")
    print(f"Database: {settings.database_url.split('@')[1]}")  # Hide credentials
    print()

    # Step 1: Check database connection
    if not await check_database_connection():
        print("\nMigration aborted: Cannot connect to database")
        sys.exit(1)

    # Step 2: Create backup
    from datetime import datetime
    backup_name = f"pre_migration_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    if not await create_backup(backup_name):
        response = input("\nBackup failed. Continue anyway? (yes/no): ")
        if response.lower() != "yes":
            print("Migration aborted by user")
            sys.exit(1)

    # Step 3: Run migrations
    print("\nRunning migrations...")
    if not run_migrations():
        print("\nMigration failed!")
        print(f"Restore from backup: {backup_name}")
        sys.exit(1)

    # Step 4: Verify migration
    if not await verify_migration():
        print("\nMigration verification failed!")
        print(f"Restore from backup: {backup_name}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("MIGRATION COMPLETED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
```

**File: `backend/scripts/rollback.py`**

```python
#!/usr/bin/env python3
"""Database rollback script."""

import sys
from alembic import command
from alembic.config import Config


def rollback_migration(steps: int = 1) -> bool:
    """Rollback database migration by N steps."""
    try:
        alembic_cfg = Config("alembic.ini")

        # Rollback
        if steps == 1:
            command.downgrade(alembic_cfg, "-1")
        else:
            command.downgrade(alembic_cfg, f"-{steps}")

        print(f"✓ Rolled back {steps} migration(s)")
        return True

    except Exception as e:
        print(f"✗ Rollback failed: {e}")
        return False


if __name__ == "__main__":
    steps = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    print(f"Rolling back {steps} migration(s)...")

    if rollback_migration(steps):
        print("Rollback completed successfully")
        sys.exit(0)
    else:
        print("Rollback failed")
        sys.exit(1)
```

---

## Observability

### Structured Logging

**File: `backend/app/observability/logging_config.py`**

```python
import logging
import sys
from datetime import datetime
from pythonjsonlogger import jsonlogger
from app.config.settings import get_settings


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields."""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)

        # Add timestamp
        log_record['timestamp'] = datetime.utcnow().isoformat()

        # Add environment
        settings = get_settings()
        log_record['environment'] = settings.environment

        # Add service name
        log_record['service'] = 'flowrex-backend'

        # Add level
        log_record['level'] = record.levelname


def setup_logging():
    """Configure application logging."""
    settings = get_settings()

    # Root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, settings.log_level.upper()))

    # Remove existing handlers
    logger.handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)

    if settings.log_format == "json":
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s'
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if enabled)
    if settings.environment != "development":
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            '/var/log/flowrex/app.log',
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Silence noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logger.info("Logging configured", extra={
        "log_level": settings.log_level,
        "log_format": settings.log_format,
    })
```

### Metrics Collection

**File: `backend/app/observability/metrics.py`**

```python
from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
from fastapi import FastAPI, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import time


# Metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

trades_executed_total = Counter(
    'trades_executed_total',
    'Total trades executed',
    ['symbol', 'side', 'execution_mode']
)

signals_generated_total = Counter(
    'signals_generated_total',
    'Total signals generated',
    ['strategy', 'signal_type']
)

active_strategies = Gauge(
    'active_strategies',
    'Number of active strategies'
)

websocket_connections = Gauge(
    'websocket_connections',
    'Number of active WebSocket connections'
)

database_connections = Gauge(
    'database_connections',
    'Number of active database connections'
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP metrics."""

    async def dispatch(self, request: Request, call_next):
        # Skip metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)

        # Record request
        start_time = time.time()

        response = await call_next(request)

        # Record metrics
        duration = time.time() - start_time

        http_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()

        http_request_duration_seconds.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)

        return response


def setup_metrics(app: FastAPI):
    """Setup metrics collection."""
    # Add middleware
    app.add_middleware(MetricsMiddleware)

    # Add metrics endpoint
    @app.get("/metrics")
    async def metrics():
        return Response(
            content=generate_latest(REGISTRY),
            media_type="text/plain"
        )
```

### Alerting Configuration

**File: `backend/config/alerts.yaml`**

```yaml
# Prometheus Alerting Rules
groups:
  - name: flowrex_alerts
    interval: 30s
    rules:
      # Application Health
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} requests/sec"

      - alert: SlowResponseTime
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Slow response time detected"
          description: "95th percentile response time is {{ $value }}s"

      # Database
      - alert: DatabaseConnectionPoolExhausted
        expr: database_connections >= 20
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Database connection pool exhausted"
          description: "Database connection pool is at {{ $value }} connections"

      - alert: DatabaseDown
        expr: up{job="postgres"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Database is down"
          description: "PostgreSQL database is not responding"

      # Trading
      - alert: NoTradesExecuted
        expr: rate(trades_executed_total[1h]) == 0
        for: 2h
        labels:
          severity: warning
        annotations:
          summary: "No trades executed in 2 hours"
          description: "Trading may be stalled"

      - alert: HighTradeFailureRate
        expr: rate(trades_failed_total[5m]) / rate(trades_attempted_total[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High trade failure rate"
          description: "Trade failure rate is {{ $value | humanizePercentage }}"

      # WebSocket
      - alert: HighWebSocketConnectionCount
        expr: websocket_connections > 90
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High WebSocket connection count"
          description: "WebSocket connections at {{ $value }}"

      # System
      - alert: HighMemoryUsage
        expr: process_resident_memory_bytes > 1e9  # 1GB
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ $value | humanize }}B"

      - alert: HighCPUUsage
        expr: rate(process_cpu_seconds_total[5m]) > 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage"
          description: "CPU usage is {{ $value | humanizePercentage }}"
```

---

## Security Hardening

### Security Headers

**File: `backend/app/middleware/security.py`**

```python
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.config.settings import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)

        # Security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' wss: https:;"
        )
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'

        return response


def setup_security(app: FastAPI):
    """Setup security middleware."""
    settings = get_settings()

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Security headers
    app.add_middleware(SecurityHeadersMiddleware)

    # Trusted hosts (production only)
    if settings.environment == "production":
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["flowrex.app", "www.flowrex.app", "api.flowrex.app"]
        )
```

### Rate Limiting

**File: `backend/app/middleware/rate_limit.py`**

```python
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Tuple
import asyncio


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, requests_per_minute: int = 60, burst: int = 10):
        self.rate = requests_per_minute / 60  # Requests per second
        self.burst = burst
        self.clients: Dict[str, Tuple[float, float]] = {}  # client_id -> (tokens, last_update)
        self._lock = asyncio.Lock()

    async def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed."""
        async with self._lock:
            now = datetime.utcnow().timestamp()

            if client_id not in self.clients:
                self.clients[client_id] = (self.burst - 1, now)
                return True

            tokens, last_update = self.clients[client_id]

            # Add tokens based on time elapsed
            elapsed = now - last_update
            tokens = min(self.burst, tokens + elapsed * self.rate)

            if tokens >= 1:
                self.clients[client_id] = (tokens - 1, now)
                return True
            else:
                self.clients[client_id] = (tokens, now)
                return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""

    def __init__(self, app, requests_per_minute: int = 60, burst: int = 10):
        super().__init__(app)
        self.limiter = RateLimiter(requests_per_minute, burst)

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks and metrics
        if request.url.path in ["/health", "/metrics"]:
            return await call_next(request)

        # Get client identifier (IP address or user ID)
        client_id = request.client.host if request.client else "unknown"

        # Check if request is allowed
        if not await self.limiter.is_allowed(client_id):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later."
            )

        return await call_next(request)
```

---

## Deployment Readiness Gates

### Pre-Deployment Checklist Script

**File: `scripts/deployment_checklist.py`**

```python
#!/usr/bin/env python3
"""Deployment readiness checker."""

import sys
import asyncio
from typing import List, Tuple


class DeploymentCheck:
    """Base class for deployment checks."""

    def __init__(self, name: str):
        self.name = name

    async def run(self) -> Tuple[bool, str]:
        """Run check. Returns (success, message)."""
        raise NotImplementedError


class TestsPassCheck(DeploymentCheck):
    """Check that all tests pass."""

    def __init__(self):
        super().__init__("Tests Pass")

    async def run(self) -> Tuple[bool, str]:
        import subprocess

        try:
            result = subprocess.run(
                ["pytest", "tests/", "-v", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0:
                return True, "All tests passed"
            else:
                return False, f"Tests failed:\n{result.stdout}\n{result.stderr}"

        except Exception as e:
            return False, f"Test execution failed: {e}"


class CoverageCheck(DeploymentCheck):
    """Check that code coverage meets threshold."""

    def __init__(self, threshold: int = 80):
        super().__init__(f"Code Coverage >= {threshold}%")
        self.threshold = threshold

    async def run(self) -> Tuple[bool, str]:
        import subprocess

        try:
            result = subprocess.run(
                ["pytest", "tests/", "--cov=app", "--cov-report=term-missing"],
                capture_output=True,
                text=True,
            )

            # Parse coverage from output
            for line in result.stdout.split('\n'):
                if 'TOTAL' in line:
                    parts = line.split()
                    coverage = int(parts[-1].replace('%', ''))
                    if coverage >= self.threshold:
                        return True, f"Coverage: {coverage}%"
                    else:
                        return False, f"Coverage too low: {coverage}% < {self.threshold}%"

            return False, "Could not parse coverage"

        except Exception as e:
            return False, f"Coverage check failed: {e}"


class DatabaseMigrationCheck(DeploymentCheck):
    """Check that migrations are up to date."""

    def __init__(self):
        super().__init__("Database Migrations Up to Date")

    async def run(self) -> Tuple[bool, str]:
        from alembic import command
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        from alembic.runtime.migration import MigrationContext
        from sqlalchemy import create_engine
        from app.config.settings import get_settings

        try:
            settings = get_settings()
            engine = create_engine(settings.database_url.replace("asyncpg", "psycopg2"))

            # Get current revision
            with engine.connect() as conn:
                context = MigrationContext.configure(conn)
                current = context.get_current_revision()

            # Get head revision
            alembic_cfg = Config("alembic.ini")
            script = ScriptDirectory.from_config(alembic_cfg)
            head = script.get_current_head()

            if current == head:
                return True, f"Migrations current (revision: {current})"
            else:
                return False, f"Migrations out of date: current={current}, head={head}"

        except Exception as e:
            return False, f"Migration check failed: {e}"


class SecretsCheck(DeploymentCheck):
    """Check that all required secrets are configured."""

    def __init__(self):
        super().__init__("Required Secrets Configured")

    async def run(self) -> Tuple[bool, str]:
        from app.config.secrets import get_secrets_manager

        try:
            secrets_manager = get_secrets_manager()
            valid, missing = secrets_manager.validate_required_secrets()

            if valid:
                return True, "All required secrets configured"
            else:
                return False, f"Missing secrets: {', '.join(missing)}"

        except Exception as e:
            return False, f"Secrets check failed: {e}"


class SecurityCheck(DeploymentCheck):
    """Check security configurations."""

    def __init__(self):
        super().__init__("Security Configuration")

    async def run(self) -> Tuple[bool, str]:
        from app.config.settings import get_settings

        try:
            settings = get_settings()
            issues = []

            # Check JWT secret
            if len(settings.jwt_secret_key) < 32:
                issues.append("JWT secret key too short")

            # Check debug mode
            if settings.debug and settings.environment == "production":
                issues.append("Debug mode enabled in production")

            # Check HTTPS in production
            if settings.environment == "production":
                if not settings.cors_origins[0].startswith("https"):
                    issues.append("CORS origins not using HTTPS")

            if issues:
                return False, f"Security issues: {', '.join(issues)}"
            else:
                return True, "Security configuration OK"

        except Exception as e:
            return False, f"Security check failed: {e}"


class DependencyCheck(DeploymentCheck):
    """Check for known vulnerabilities in dependencies."""

    def __init__(self):
        super().__init__("Dependency Security")

    async def run(self) -> Tuple[bool, str]:
        import subprocess

        try:
            # Check Python dependencies with safety
            result = subprocess.run(
                ["pip", "list", "--format=json"],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                return True, "Dependencies checked"
            else:
                return False, "Dependency check failed"

        except FileNotFoundError:
            # safety not installed, skip check
            return True, "Dependency check skipped (safety not installed)"
        except Exception as e:
            return False, f"Dependency check failed: {e}"


class LintCheck(DeploymentCheck):
    """Check code quality with linters."""

    def __init__(self):
        super().__init__("Code Quality (Linting)")

    async def run(self) -> Tuple[bool, str]:
        import subprocess

        try:
            # Run ruff (fast Python linter)
            result = subprocess.run(
                ["ruff", "check", "app/"],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                return True, "Linting passed"
            else:
                return False, f"Linting failed:\n{result.stdout}"

        except FileNotFoundError:
            return True, "Linting skipped (ruff not installed)"
        except Exception as e:
            return False, f"Lint check failed: {e}"


async def run_deployment_checks(environment: str) -> bool:
    """Run all deployment checks."""
    print("=" * 60)
    print(f"DEPLOYMENT READINESS CHECK - {environment.upper()}")
    print("=" * 60)
    print()

    checks: List[DeploymentCheck] = [
        TestsPassCheck(),
        CoverageCheck(threshold=80),
        DatabaseMigrationCheck(),
        SecretsCheck(),
        SecurityCheck(),
        DependencyCheck(),
        LintCheck(),
    ]

    results = []
    for check in checks:
        print(f"Running: {check.name}...", end=" ")
        success, message = await check.run()

        if success:
            print("✓ PASS")
            print(f"  {message}")
        else:
            print("✗ FAIL")
            print(f"  {message}")

        results.append(success)
        print()

    # Summary
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"RESULTS: {passed}/{total} checks passed")
    print("=" * 60)

    if all(results):
        print("\n✓ DEPLOYMENT READY")
        return True
    else:
        print("\n✗ DEPLOYMENT BLOCKED")
        print("Fix the failing checks before deploying.")
        return False


async def main():
    environment = sys.argv[1] if len(sys.argv) > 1 else "staging"
    ready = await run_deployment_checks(environment)
    sys.exit(0 if ready else 1)


if __name__ == "__main__":
    asyncio.run(main())
```

---

## CI/CD Pipeline

### GitHub Actions Workflow

**File: `.github/workflows/deploy.yml`**

```yaml
name: Deploy to Staging/Production

on:
  push:
    branches:
      - main        # Deploy to staging
      - production  # Deploy to production

jobs:
  test:
    name: Run Tests
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: flowrex
          POSTGRES_PASSWORD: testpassword
          POSTGRES_DB: flowrex_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio

      - name: Run tests
        env:
          DATABASE_URL: postgresql+asyncpg://flowrex:testpassword@localhost:5432/flowrex_test
          REDIS_URL: redis://localhost:6379/0
          JWT_SECRET_KEY: test-secret-key-min-32-chars-long-for-testing
        run: |
          cd backend
          pytest tests/ -v --cov=app --cov-report=xml --cov-fail-under=80

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./backend/coverage.xml

  lint:
    name: Lint Code
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install ruff
        run: pip install ruff

      - name: Run ruff
        run: ruff check backend/app

  security:
    name: Security Scan
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          severity: 'CRITICAL,HIGH'

  build-backend:
    name: Build Backend Image
    runs-on: ubuntu-latest
    needs: [test, lint, security]

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ secrets.REGISTRY_URL }}
          username: ${{ secrets.REGISTRY_USERNAME }}
          password: ${{ secrets.REGISTRY_PASSWORD }}

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: ./backend
          push: true
          tags: |
            ${{ secrets.REGISTRY_URL }}/flowrex-backend:${{ github.sha }}
            ${{ secrets.REGISTRY_URL }}/flowrex-backend:latest
          cache-from: type=registry,ref=${{ secrets.REGISTRY_URL }}/flowrex-backend:latest
          cache-to: type=inline

  build-frontend:
    name: Build Frontend
    runs-on: ubuntu-latest
    needs: [lint]

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install dependencies
        run: |
          cd frontend
          npm ci

      - name: Build
        run: |
          cd frontend
          npm run build

      - name: Upload build artifacts
        uses: actions/upload-artifact@v3
        with:
          name: frontend-build
          path: frontend/.next

  deploy-staging:
    name: Deploy to Staging
    runs-on: ubuntu-latest
    needs: [build-backend, build-frontend]
    if: github.ref == 'refs/heads/main'
    environment: staging

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Deploy to staging
        run: |
          # This would typically use kubectl, helm, or deployment scripts
          echo "Deploying to staging environment..."
          # kubectl apply -f k8s/staging/
          # helm upgrade --install flowrex ./helm-chart --namespace staging

  deploy-production:
    name: Deploy to Production
    runs-on: ubuntu-latest
    needs: [build-backend, build-frontend]
    if: github.ref == 'refs/heads/production'
    environment: production

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Run deployment checks
        run: |
          cd backend
          python scripts/deployment_checklist.py production

      - name: Deploy to production
        run: |
          echo "Deploying to production environment..."
          # kubectl apply -f k8s/production/
          # helm upgrade --install flowrex ./helm-chart --namespace production

      - name: Verify deployment
        run: |
          echo "Verifying deployment..."
          # kubectl rollout status deployment/flowrex-backend -n production
          # curl https://api.flowrex.app/health

      - name: Notify deployment
        uses: 8398a7/action-slack@v3
        with:
          status: ${{ job.status }}
          text: 'Production deployment completed'
          webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

---

## Validation Checklist

Before proceeding to deployment, Opus MUST verify:

### Environment Configuration
- [ ] .env.example file created with all required variables
- [ ] Environment-specific .env files created (dev, staging, prod)
- [ ] All secrets identified and documented
- [ ] Secrets management strategy implemented
- [ ] SecretsManager class validates required secrets
- [ ] Settings class loads from environment and secrets

### Database Management
- [ ] Migration script with safety checks implemented
- [ ] Rollback script implemented
- [ ] Backup strategy defined and tested
- [ ] Migration creates backup before running
- [ ] Migration verifies success after running
- [ ] Database connection pooling configured

### Observability
- [ ] Structured JSON logging configured
- [ ] Log levels configurable per environment
- [ ] Prometheus metrics exported
- [ ] Key business metrics tracked (trades, signals, errors)
- [ ] Alert rules defined in alerts.yaml
- [ ] Critical alerts identified

### Security
- [ ] Security headers middleware implemented
- [ ] CORS configured correctly
- [ ] Rate limiting implemented
- [ ] HTTPS enforced in production
- [ ] JWT secrets validated (min 32 chars)
- [ ] Sensitive data not logged

### Deployment Readiness
- [ ] Deployment checklist script implemented
- [ ] All checks defined (tests, coverage, migrations, secrets, security)
- [ ] CI/CD pipeline configured
- [ ] Build process automated
- [ ] Deployment gates prevent broken deploys
- [ ] Test coverage threshold enforced (80%)

### CI/CD Pipeline
- [ ] GitHub Actions workflow created
- [ ] Tests run on every push
- [ ] Linting enforced
- [ ] Security scanning enabled
- [ ] Docker images built and pushed
- [ ] Staging deploys from main branch
- [ ] Production deploys from production branch
- [ ] Deployment verification steps included

---

## Hard Stop Criteria - DO NOT PROCEED if:

1. **Tests failing** - Any test failures block deployment
2. **Coverage below threshold** - Code coverage must be ≥80%
3. **Missing secrets** - Required secrets not configured
4. **Security vulnerabilities** - Known high/critical vulnerabilities in dependencies
5. **Migrations out of sync** - Database migrations not up to date
6. **Debug mode in production** - Debug mode must be disabled in production
7. **Weak JWT secret** - JWT secret less than 32 characters
8. **No backup strategy** - Database backup process not implemented
9. **No rollback plan** - Rollback procedure not tested
10. **Deployment checklist fails** - Any deployment readiness check fails

---

## Integration Notes

**Testing** (from 15_TESTING_AND_VALIDATION.md):
- Deployment gates enforce test passage
- Coverage thresholds block low-quality code
- CI pipeline runs full test suite

**Settings** (from 14_SETTINGS_AND_MODES.md):
- Settings loaded from environment and secrets
- Hard caps remain immutable across environments
- Mode awareness (GUIDE/AUTONOMOUS) respected

**Security**:
- Secrets never committed to version control
- Rate limiting prevents abuse
- Security headers protect against common attacks

---

END OF PROMPT 17
