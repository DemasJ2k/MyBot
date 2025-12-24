# 18_PRODUCTION_DEPLOYMENT.md

## Purpose and Scope

This prompt instructs Opus 4.5 to deploy the Flowrex trading platform to production with comprehensive containerization, orchestration, monitoring, and operational procedures that ensure high availability, security, and compliance.

**Core Principles:**
1. **Zero Downtime**: Rolling deployments with health checks
2. **Observability**: Comprehensive monitoring and alerting
3. **Security**: Defense in depth with multiple security layers
4. **Scalability**: Horizontal scaling for backend services
5. **Reliability**: Auto-recovery, backups, and disaster recovery
6. **Compliance**: Audit trails and data protection

**Integration Points:**
- Builds on DEPLOYMENT_PREP.md (prompt 17) for pre-deployment validation
- Uses all system components in production mode
- Enforces RISK_ENGINE.md (prompt 09) hard caps in production

---

## Production Architecture

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      INTERNET                                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  CLOUDFLARE CDN                              │
│             (DDoS Protection, SSL, WAF)                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  LOAD BALANCER                               │
│            (NGINX / AWS ALB / GCP LB)                        │
└──────────┬────────────────────────────┬─────────────────────┘
           │                            │
           ▼                            ▼
┌──────────────────────┐    ┌──────────────────────┐
│   FRONTEND (Next.js) │    │  BACKEND (FastAPI)   │
│   - Server-Side      │    │  - API Endpoints     │
│   - Static Assets    │    │  - WebSockets        │
│   - 3 replicas       │    │  - 5 replicas        │
└──────────┬───────────┘    └──────────┬───────────┘
           │                           │
           │                           ├──────────┐
           │                           │          │
           ▼                           ▼          ▼
┌──────────────────────┐    ┌─────────────────────────┐
│   PostgreSQL 16      │    │      Redis 7            │
│   - Primary          │    │   - Cache               │
│   - 2 Read Replicas  │    │   - Sessions            │
│   - Automated Backup │    │   - WebSocket State     │
└──────────────────────┘    └─────────────────────────┘
           │
           ▼
┌──────────────────────┐
│   S3-Compatible      │
│   Object Storage     │
│   - Backups          │
│   - Logs             │
│   - Exports          │
└──────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              MONITORING & OBSERVABILITY                      │
│   - Prometheus + Grafana                                     │
│   - Sentry (Error Tracking)                                  │
│   - CloudWatch / Stackdriver                                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              EXTERNAL SERVICES                               │
│   - TwelveData API (Market Data)                            │
│   - OANDA / MT5 (Brokers)                                   │
│   - SendGrid (Email)                                        │
└─────────────────────────────────────────────────────────────┘
```

### Infrastructure Components

**Compute:**
- Backend: 5 containers (t3.medium or equivalent)
- Frontend: 3 containers (t3.small or equivalent)
- Workers: 2 containers for background tasks

**Database:**
- PostgreSQL 16 (db.r6g.xlarge or equivalent)
- Primary + 2 read replicas
- Automated daily backups with 30-day retention
- Point-in-time recovery enabled

**Cache:**
- Redis 7 (cache.r6g.large or equivalent)
- Persistence enabled (RDB + AOF)
- Multi-AZ deployment

**Storage:**
- S3 or compatible object storage
- Separate buckets for backups, logs, exports
- Lifecycle policies for cost optimization

**Networking:**
- VPC with public and private subnets
- NAT Gateway for outbound traffic
- Security groups with least-privilege access
- SSL/TLS everywhere (Let's Encrypt or ACM)

---

## Containerization

### Backend Dockerfile

**File: `backend/Dockerfile`**

```dockerfile
# Multi-stage build for production
FROM python:3.12-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user
RUN useradd -m -u 1000 flowrex && \
    mkdir -p /app /var/log/flowrex && \
    chown -R flowrex:flowrex /app /var/log/flowrex

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=flowrex:flowrex . .

# Switch to non-root user
USER flowrex

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Frontend Dockerfile

**File: `frontend/Dockerfile`**

```dockerfile
# Build stage
FROM node:20-alpine as builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy application code
COPY . .

# Build application
ENV NEXT_TELEMETRY_DISABLED 1
RUN npm run build

# Production stage
FROM node:20-alpine

# Install dumb-init for proper signal handling
RUN apk add --no-cache dumb-init

# Create non-root user
RUN addgroup -g 1000 flowrex && \
    adduser -D -u 1000 -G flowrex flowrex

WORKDIR /app

# Copy built application
COPY --from=builder --chown=flowrex:flowrex /app/.next ./.next
COPY --from=builder --chown=flowrex:flowrex /app/node_modules ./node_modules
COPY --from=builder --chown=flowrex:flowrex /app/package.json ./package.json
COPY --from=builder --chown=flowrex:flowrex /app/public ./public

# Switch to non-root user
USER flowrex

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000/api/health', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})"

# Run application
ENTRYPOINT ["dumb-init", "--"]
CMD ["npm", "start"]
```

### Docker Compose (Production)

**File: `docker-compose.prod.yml`**

```yaml
version: '3.9'

services:
  backend:
    image: ${REGISTRY_URL}/flowrex-backend:${VERSION:-latest}
    container_name: flowrex-backend
    restart: unless-stopped
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - TWELVEDATA_API_KEY=${TWELVEDATA_API_KEY}
      - OANDA_API_KEY=${OANDA_API_KEY}
      - SENTRY_DSN=${SENTRY_DSN}
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    deploy:
      replicas: 5
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
    networks:
      - flowrex-network
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  frontend:
    image: ${REGISTRY_URL}/flowrex-frontend:${VERSION:-latest}
    container_name: flowrex-frontend
    restart: unless-stopped
    environment:
      - NODE_ENV=production
      - NEXT_PUBLIC_API_URL=${API_URL}
      - NEXT_PUBLIC_WS_URL=${WS_URL}
    ports:
      - "3000:3000"
    healthcheck:
      test: ["CMD", "node", "-e", "require('http').get('http://localhost:3000/api/health', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '1'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
    networks:
      - flowrex-network
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  nginx:
    image: nginx:alpine
    container_name: flowrex-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - ./nginx/logs:/var/log/nginx
    depends_on:
      - backend
      - frontend
    networks:
      - flowrex-network
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  prometheus:
    image: prom/prometheus:latest
    container_name: flowrex-prometheus
    restart: unless-stopped
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    ports:
      - "9090:9090"
    networks:
      - flowrex-network

  grafana:
    image: grafana/grafana:latest
    container_name: flowrex-grafana
    restart: unless-stopped
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - grafana-data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources:ro
    ports:
      - "3001:3000"
    networks:
      - flowrex-network

networks:
  flowrex-network:
    driver: bridge

volumes:
  prometheus-data:
  grafana-data:
```

### NGINX Configuration

**File: `nginx/nginx.conf`**

```nginx
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 4096;
    use epoll;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for" '
                    'rt=$request_time uct="$upstream_connect_time" '
                    'uht="$upstream_header_time" urt="$upstream_response_time"';

    access_log /var/log/nginx/access.log main;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 10M;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript
               application/json application/javascript application/xml+rss;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=60r/m;
    limit_req_zone $binary_remote_addr zone=ws_limit:10m rate=10r/s;

    # Upstream backend
    upstream backend {
        least_conn;
        server backend:8000 max_fails=3 fail_timeout=30s;
        keepalive 32;
    }

    # Upstream frontend
    upstream frontend {
        least_conn;
        server frontend:3000 max_fails=3 fail_timeout=30s;
        keepalive 32;
    }

    # HTTP -> HTTPS redirect
    server {
        listen 80;
        server_name flowrex.app www.flowrex.app;

        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        location / {
            return 301 https://$server_name$request_uri;
        }
    }

    # HTTPS server
    server {
        listen 443 ssl http2;
        server_name flowrex.app www.flowrex.app;

        # SSL configuration
        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
        ssl_prefer_server_ciphers off;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 10m;
        ssl_stapling on;
        ssl_stapling_verify on;

        # Security headers
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Frame-Options "DENY" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;

        # API routes
        location /api/ {
            limit_req zone=api_limit burst=10 nodelay;

            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_buffering off;
            proxy_request_buffering off;
            proxy_read_timeout 300s;
            proxy_connect_timeout 75s;
        }

        # WebSocket routes
        location /ws {
            limit_req zone=ws_limit burst=5 nodelay;

            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 86400;
        }

        # Metrics endpoint (internal only)
        location /metrics {
            allow 10.0.0.0/8;
            deny all;
            proxy_pass http://backend;
        }

        # Health check
        location /health {
            access_log off;
            proxy_pass http://backend;
        }

        # Frontend
        location / {
            proxy_pass http://frontend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_cache_bypass $http_upgrade;
        }

        # Static assets caching
        location /_next/static/ {
            proxy_pass http://frontend;
            add_header Cache-Control "public, max-age=31536000, immutable";
        }
    }
}
```

---

## Health Checks

### Backend Health Check Endpoint

**File: `backend/app/api/health.py`**

```python
from fastapi import APIRouter, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.config.settings import get_settings
import redis.asyncio as redis
from datetime import datetime

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "flowrex-backend",
    }


@router.get("/health/ready")
async def readiness_check(response: Response):
    """Readiness check with dependency validation."""
    checks = {
        "database": False,
        "redis": False,
    }
    healthy = True

    settings = get_settings()

    # Check database
    try:
        from app.database import engine
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as e:
        healthy = False
        checks["database_error"] = str(e)

    # Check Redis
    try:
        redis_client = redis.from_url(settings.redis_url)
        await redis_client.ping()
        await redis_client.close()
        checks["redis"] = True
    except Exception as e:
        healthy = False
        checks["redis_error"] = str(e)

    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if healthy else "not_ready",
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/health/live")
async def liveness_check():
    """Liveness check."""
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
    }
```

### Frontend Health Check

**File: `frontend/app/api/health/route.ts`**

```typescript
import { NextResponse } from 'next/server'

export async function GET() {
  return NextResponse.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    service: 'flowrex-frontend',
  })
}
```

---

## Monitoring and Alerting

### Prometheus Configuration

**File: `monitoring/prometheus.yml`**

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'flowrex-production'
    environment: 'prod'

# Alertmanager configuration
alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

# Load rules
rule_files:
  - "alerts.yml"

# Scrape configurations
scrape_configs:
  # Backend metrics
  - job_name: 'flowrex-backend'
    static_configs:
      - targets: ['backend:9090']
    metrics_path: '/metrics'

  # Node exporter (system metrics)
  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']

  # PostgreSQL exporter
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  # Redis exporter
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

  # NGINX exporter
  - job_name: 'nginx'
    static_configs:
      - targets: ['nginx-exporter:9113']
```

### Grafana Dashboard

**File: `monitoring/grafana/dashboards/flowrex-overview.json`**

```json
{
  "dashboard": {
    "title": "Flowrex Production Overview",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Error Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total{status=~\"5..\"}[5m])"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Response Time (p95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Trades Executed",
        "targets": [
          {
            "expr": "increase(trades_executed_total[1h])"
          }
        ],
        "type": "stat"
      },
      {
        "title": "Active Strategies",
        "targets": [
          {
            "expr": "active_strategies"
          }
        ],
        "type": "gauge"
      },
      {
        "title": "WebSocket Connections",
        "targets": [
          {
            "expr": "websocket_connections"
          }
        ],
        "type": "gauge"
      },
      {
        "title": "Database Connections",
        "targets": [
          {
            "expr": "database_connections"
          }
        ],
        "type": "gauge"
      },
      {
        "title": "CPU Usage",
        "targets": [
          {
            "expr": "rate(process_cpu_seconds_total[5m])"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Memory Usage",
        "targets": [
          {
            "expr": "process_resident_memory_bytes"
          }
        ],
        "type": "graph"
      }
    ]
  }
}
```

---

## Deployment Process

### Zero-Downtime Deployment Script

**File: `scripts/deploy.sh`**

```bash
#!/bin/bash
set -e

# Configuration
ENVIRONMENT="${1:-staging}"
VERSION="${2:-latest}"
REGISTRY_URL="${REGISTRY_URL}"
HEALTH_CHECK_URL="https://api.flowrex.app/health/ready"
MAX_HEALTH_CHECK_ATTEMPTS=30
HEALTH_CHECK_INTERVAL=10

echo "================================================"
echo "DEPLOYING FLOWREX - ${ENVIRONMENT}"
echo "================================================"
echo "Version: ${VERSION}"
echo "Registry: ${REGISTRY_URL}"
echo ""

# Step 1: Pre-deployment checks
echo "[1/8] Running pre-deployment checks..."
cd backend
python scripts/deployment_checklist.py ${ENVIRONMENT}
if [ $? -ne 0 ]; then
    echo "❌ Pre-deployment checks failed. Aborting."
    exit 1
fi
cd ..

# Step 2: Pull latest images
echo "[2/8] Pulling latest Docker images..."
docker pull ${REGISTRY_URL}/flowrex-backend:${VERSION}
docker pull ${REGISTRY_URL}/flowrex-frontend:${VERSION}

# Step 3: Backup database
echo "[3/8] Creating database backup..."
BACKUP_NAME="pre_deploy_$(date +%Y%m%d_%H%M%S)"
cd backend
python scripts/migrate.py --backup-only --name ${BACKUP_NAME}
cd ..

# Step 4: Run database migrations
echo "[4/8] Running database migrations..."
cd backend
python scripts/migrate.py
cd ..

# Step 5: Deploy backend (rolling update)
echo "[5/8] Deploying backend..."

# Get current running containers
BACKEND_CONTAINERS=$(docker ps --filter "name=flowrex-backend" --format "{{.ID}}")
BACKEND_COUNT=$(echo ${BACKEND_CONTAINERS} | wc -w)

# Start new containers
docker-compose -f docker-compose.prod.yml up -d --scale backend=$((BACKEND_COUNT + 1)) --no-recreate backend

# Wait for new containers to be healthy
echo "Waiting for new backend containers to be healthy..."
sleep 30

# Check health
HEALTHY=false
for i in $(seq 1 ${MAX_HEALTH_CHECK_ATTEMPTS}); do
    if curl -f -s ${HEALTH_CHECK_URL} > /dev/null; then
        HEALTHY=true
        break
    fi
    echo "Health check attempt ${i}/${MAX_HEALTH_CHECK_ATTEMPTS} failed. Retrying in ${HEALTH_CHECK_INTERVAL}s..."
    sleep ${HEALTH_CHECK_INTERVAL}
done

if [ "${HEALTHY}" = false ]; then
    echo "❌ New backend containers failed health check. Rolling back..."
    docker-compose -f docker-compose.prod.yml up -d --scale backend=${BACKEND_COUNT} --no-recreate backend
    exit 1
fi

# Remove old containers
echo "Removing old backend containers..."
for container in ${BACKEND_CONTAINERS}; do
    docker stop ${container}
    docker rm ${container}
done

# Scale to desired count
docker-compose -f docker-compose.prod.yml up -d --scale backend=5 --no-recreate backend

# Step 6: Deploy frontend (rolling update)
echo "[6/8] Deploying frontend..."

# Similar rolling update for frontend
FRONTEND_CONTAINERS=$(docker ps --filter "name=flowrex-frontend" --format "{{.ID}}")
FRONTEND_COUNT=$(echo ${FRONTEND_CONTAINERS} | wc -w)

docker-compose -f docker-compose.prod.yml up -d --scale frontend=$((FRONTEND_COUNT + 1)) --no-recreate frontend

sleep 20

# Remove old frontend containers
for container in ${FRONTEND_CONTAINERS}; do
    docker stop ${container}
    docker rm ${container}
done

docker-compose -f docker-compose.prod.yml up -d --scale frontend=3 --no-recreate frontend

# Step 7: Reload NGINX
echo "[7/8] Reloading NGINX..."
docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload

# Step 8: Post-deployment validation
echo "[8/8] Running post-deployment validation..."

# Check all endpoints
ENDPOINTS=(
    "${HEALTH_CHECK_URL}"
    "https://api.flowrex.app/health/live"
    "https://flowrex.app"
)

ALL_HEALTHY=true
for endpoint in "${ENDPOINTS[@]}"; do
    echo "Checking ${endpoint}..."
    if curl -f -s ${endpoint} > /dev/null; then
        echo "✅ ${endpoint} is healthy"
    else
        echo "❌ ${endpoint} is not healthy"
        ALL_HEALTHY=false
    fi
done

if [ "${ALL_HEALTHY}" = false ]; then
    echo "❌ Post-deployment validation failed!"
    echo "Consider rolling back to previous version."
    exit 1
fi

echo ""
echo "================================================"
echo "✅ DEPLOYMENT SUCCESSFUL"
echo "================================================"
echo "Environment: ${ENVIRONMENT}"
echo "Version: ${VERSION}"
echo "Timestamp: $(date)"
echo ""

# Send notification
curl -X POST ${SLACK_WEBHOOK_URL} \
    -H 'Content-Type: application/json' \
    -d "{\"text\":\"✅ Flowrex ${ENVIRONMENT} deployment successful - ${VERSION}\"}"
```

### Rollback Script

**File: `scripts/rollback.sh`**

```bash
#!/bin/bash
set -e

PREVIOUS_VERSION="${1}"
BACKUP_NAME="${2}"

echo "================================================"
echo "ROLLING BACK DEPLOYMENT"
echo "================================================"
echo "Target version: ${PREVIOUS_VERSION}"
echo "Database backup: ${BACKUP_NAME}"
echo ""

# Step 1: Rollback database
if [ -n "${BACKUP_NAME}" ]; then
    echo "[1/3] Rolling back database..."
    cd backend
    python scripts/restore_backup.py ${BACKUP_NAME}
    cd ..
else
    echo "[1/3] Skipping database rollback (no backup specified)"
fi

# Step 2: Deploy previous version
echo "[2/3] Deploying previous version..."
export VERSION=${PREVIOUS_VERSION}
docker-compose -f docker-compose.prod.yml up -d

# Step 3: Verify health
echo "[3/3] Verifying health..."
sleep 30

if curl -f -s https://api.flowrex.app/health/ready > /dev/null; then
    echo "✅ Rollback successful"
else
    echo "❌ Rollback failed - manual intervention required"
    exit 1
fi

echo "================================================"
echo "ROLLBACK COMPLETE"
echo "================================================"
```

---

## Incident Response

### Incident Response Playbook

**File: `docs/incident-response-playbook.md`**

```markdown
# Incident Response Playbook

## Severity Levels

**P0 - Critical**
- Complete system outage
- Data loss or corruption
- Security breach
- Response time: Immediate

**P1 - High**
- Partial outage (single service down)
- Significant performance degradation
- Response time: 15 minutes

**P2 - Medium**
- Minor degradation
- Non-critical feature broken
- Response time: 1 hour

**P3 - Low**
- Cosmetic issues
- Nice-to-have features
- Response time: Next business day

## Incident Response Process

### 1. Detection
- Automated alerts via Prometheus/Grafana
- User reports
- Monitoring dashboard anomalies

### 2. Triage
- Assess severity level
- Assign incident commander
- Create incident channel (#incident-YYYYMMDD-HHMM)
- Page on-call engineer (P0/P1 only)

### 3. Investigation
- Check logs: `docker-compose logs -f backend`
- Check metrics: Grafana dashboard
- Check error tracking: Sentry
- Check database: Connection count, slow queries
- Check external services: TwelveData, OANDA status

### 4. Mitigation
- Apply immediate fix if known
- Rollback to previous version if needed
- Scale up resources if capacity issue
- Enable maintenance mode if necessary

### 5. Resolution
- Deploy permanent fix
- Verify resolution
- Monitor for regression
- Update incident tracker

### 6. Post-Mortem
- Document timeline
- Identify root cause
- Define action items
- Schedule review meeting

## Common Incidents

### Database Connection Pool Exhausted

**Symptoms:**
- `database_connections` metric at max
- Slow API responses
- 500 errors

**Investigation:**
```bash
# Check active connections
docker-compose exec postgres psql -U flowrex -c "SELECT count(*) FROM pg_stat_activity;"

# Check long-running queries
docker-compose exec postgres psql -U flowrex -c "SELECT pid, now() - query_start AS duration, query FROM pg_stat_activity WHERE state = 'active' ORDER BY duration DESC;"
```

**Mitigation:**
```bash
# Kill long-running queries
docker-compose exec postgres psql -U flowrex -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'active' AND now() - query_start > interval '5 minutes';"

# Increase pool size (temporary)
# Update DATABASE_POOL_SIZE environment variable and restart
```

### High Error Rate

**Symptoms:**
- Error rate > 5%
- 500 errors in logs
- Sentry alerts

**Investigation:**
```bash
# Check recent errors
docker-compose logs --tail=100 backend | grep ERROR

# Check Sentry for error details
# https://sentry.io/flowrex/errors
```

**Mitigation:**
- If known bug: Deploy hotfix
- If external service: Check service status page
- If unknown: Rollback to previous version

### Trade Execution Failures

**Symptoms:**
- `trades_failed_total` metric increasing
- User reports trades not executing

**Investigation:**
```bash
# Check broker connectivity
docker-compose exec backend python -c "from app.execution.adapters.oanda_adapter import OandaAdapter; import asyncio; asyncio.run(OandaAdapter().connect())"

# Check recent failed trades
docker-compose exec postgres psql -U flowrex -c "SELECT * FROM trades WHERE status = 'failed' ORDER BY created_at DESC LIMIT 10;"
```

**Mitigation:**
- Check broker API status
- Verify API credentials
- Check risk engine blocks (might be hitting hard caps)
- Check account balance

### WebSocket Disconnections

**Symptoms:**
- `websocket_connections` dropping
- User reports real-time updates not working

**Investigation:**
```bash
# Check WebSocket errors
docker-compose logs --tail=100 backend | grep "websocket"

# Check NGINX WebSocket proxy config
docker-compose exec nginx cat /etc/nginx/nginx.conf | grep -A10 "location /ws"
```

**Mitigation:**
- Restart backend service
- Check NGINX timeout settings
- Check Redis (WebSocket state storage)

## Emergency Shutdown

**When to use:**
- Security breach detected
- Runaway trading (exceeds risk limits)
- Data corruption risk

**Procedure:**
```bash
# 1. Enable emergency mode (disables all trading)
docker-compose exec backend python -c "from app.services.emergency_service import EmergencyService; import asyncio; asyncio.run(EmergencyService().enable_emergency_mode())"

# 2. Close all open positions
docker-compose exec backend python -c "from app.services.execution_service import ExecutionService; import asyncio; asyncio.run(ExecutionService().close_all_positions())"

# 3. Enable maintenance mode (block new requests)
docker-compose exec nginx sh -c "echo 'maintenance mode' > /usr/share/nginx/html/maintenance.html"
# Update NGINX config to return 503 for all requests

# 4. Investigate root cause

# 5. When resolved, disable maintenance mode
# Revert NGINX config
docker-compose exec nginx nginx -s reload

# 6. Disable emergency mode
docker-compose exec backend python -c "from app.services.emergency_service import EmergencyService; import asyncio; asyncio.run(EmergencyService().disable_emergency_mode())"
```
```

---

## Backup and Disaster Recovery

### Automated Backup Script

**File: `scripts/backup.sh`**

```bash
#!/bin/bash
set -e

# Configuration
BACKUP_DIR="/backups"
S3_BUCKET="${BACKUP_S3_BUCKET}"
RETENTION_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "================================================"
echo "DATABASE BACKUP - ${TIMESTAMP}"
echo "================================================"

# Create backup directory
mkdir -p ${BACKUP_DIR}

# Backup database
echo "Creating database backup..."
docker-compose exec -T postgres pg_dump -U flowrex -Fc flowrex > ${BACKUP_DIR}/flowrex_${TIMESTAMP}.dump

# Compress backup
echo "Compressing backup..."
gzip ${BACKUP_DIR}/flowrex_${TIMESTAMP}.dump

# Upload to S3
echo "Uploading to S3..."
aws s3 cp ${BACKUP_DIR}/flowrex_${TIMESTAMP}.dump.gz s3://${S3_BUCKET}/backups/

# Clean up old backups
echo "Cleaning up old backups..."
find ${BACKUP_DIR} -name "flowrex_*.dump.gz" -mtime +${RETENTION_DAYS} -delete

# Clean up old S3 backups
aws s3 ls s3://${S3_BUCKET}/backups/ | while read -r line; do
    created_date=$(echo $line | awk '{print $1" "$2}')
    created_timestamp=$(date -d "$created_date" +%s)
    current_timestamp=$(date +%s)
    days_old=$(( (current_timestamp - created_timestamp) / 86400 ))

    if [ $days_old -gt $RETENTION_DAYS ]; then
        file_name=$(echo $line | awk '{print $4}')
        aws s3 rm s3://${S3_BUCKET}/backups/${file_name}
    fi
done

echo "✅ Backup complete: flowrex_${TIMESTAMP}.dump.gz"
```

### Restore Script

**File: `scripts/restore.sh`**

```bash
#!/bin/bash
set -e

BACKUP_FILE="${1}"

if [ -z "${BACKUP_FILE}" ]; then
    echo "Usage: ./restore.sh <backup_file>"
    exit 1
fi

echo "================================================"
echo "DATABASE RESTORE"
echo "================================================"
echo "Backup file: ${BACKUP_FILE}"
echo ""

read -p "This will OVERWRITE the current database. Are you sure? (yes/no): " confirm
if [ "${confirm}" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

# Download from S3 if needed
if [[ ${BACKUP_FILE} == s3://* ]]; then
    echo "Downloading backup from S3..."
    aws s3 cp ${BACKUP_FILE} /tmp/restore.dump.gz
    BACKUP_FILE=/tmp/restore.dump.gz
fi

# Decompress if gzipped
if [[ ${BACKUP_FILE} == *.gz ]]; then
    echo "Decompressing backup..."
    gunzip -c ${BACKUP_FILE} > /tmp/restore.dump
    BACKUP_FILE=/tmp/restore.dump
fi

# Stop backend to prevent connections
echo "Stopping backend..."
docker-compose stop backend

# Drop existing connections
echo "Dropping existing connections..."
docker-compose exec postgres psql -U flowrex -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'flowrex' AND pid <> pg_backend_pid();"

# Restore database
echo "Restoring database..."
docker-compose exec -T postgres pg_restore -U flowrex -d flowrex --clean --if-exists < ${BACKUP_FILE}

# Start backend
echo "Starting backend..."
docker-compose start backend

echo "✅ Restore complete"
```

---

## Compliance and Audit

### Audit Trail Configuration

**File: `backend/app/middleware/audit.py`**

```python
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime
import logging

audit_logger = logging.getLogger("audit")


class AuditMiddleware(BaseHTTPMiddleware):
    """Log all requests for compliance and audit."""

    async def dispatch(self, request: Request, call_next):
        # Extract user info
        user_id = getattr(request.state, "user_id", None)

        # Log request
        audit_logger.info("request", extra={
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "method": request.method,
            "path": request.url.path,
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        })

        # Process request
        response = await call_next(request)

        # Log response
        audit_logger.info("response", extra={
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
        })

        return response
```

### GDPR Data Export

**File: `backend/app/api/v1/data_export_routes.py`**

```python
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
import json

router = APIRouter(prefix="/data-export", tags=["data-export"])


@router.post("/request")
async def request_data_export(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Request GDPR data export."""
    background_tasks.add_task(generate_data_export, current_user.id, db)

    return {
        "message": "Data export requested. You will receive an email when ready.",
        "user_id": current_user.id,
    }


async def generate_data_export(user_id: int, db: AsyncSession):
    """Generate complete data export for user."""
    # Fetch all user data
    user_data = {
        "user": {},  # User profile
        "strategies": [],  # Strategies
        "signals": [],  # Signals
        "trades": [],  # Trades
        "journal_entries": [],  # Journal entries
        "settings": {},  # User settings
    }

    # Export to JSON
    export_json = json.dumps(user_data, indent=2)

    # Upload to S3
    # Send email to user with download link
    # ...
```

---

## Validation Checklist

Before deploying to production, Opus MUST verify:

### Infrastructure
- [ ] VPC and networking configured
- [ ] Security groups configured with least privilege
- [ ] SSL certificates installed and valid
- [ ] Load balancer configured with health checks
- [ ] Auto-scaling configured for backend
- [ ] Database replicas configured
- [ ] Redis persistence enabled
- [ ] S3 buckets created for backups and logs

### Containerization
- [ ] Backend Dockerfile builds successfully
- [ ] Frontend Dockerfile builds successfully
- [ ] Images pushed to container registry
- [ ] Images scanned for vulnerabilities
- [ ] Health checks configured in Dockerfiles
- [ ] Non-root users used in containers
- [ ] Resource limits set

### Deployment
- [ ] Zero-downtime deployment script tested
- [ ] Rollback script tested
- [ ] Database migration script tested
- [ ] Backup script tested
- [ ] Restore script tested
- [ ] Health check endpoints return 200
- [ ] Load balancer routes traffic correctly

### Monitoring
- [ ] Prometheus scraping metrics
- [ ] Grafana dashboards configured
- [ ] Alert rules configured
- [ ] Alerting destinations configured (Slack, PagerDuty)
- [ ] Sentry error tracking configured
- [ ] Log aggregation configured

### Security
- [ ] HTTPS enforced everywhere
- [ ] Security headers configured in NGINX
- [ ] Rate limiting enabled
- [ ] Secrets stored in secrets manager
- [ ] Database credentials rotated
- [ ] Firewall rules configured
- [ ] Audit logging enabled

### Compliance
- [ ] Audit middleware enabled
- [ ] Data export functionality tested
- [ ] Data retention policies implemented
- [ ] Privacy policy updated
- [ ] Terms of service updated

---

## Hard Stop Criteria - DO NOT DEPLOY if:

1. **Health checks failing** - Any service health check returns non-200
2. **Tests failing** - Any test failures in CI pipeline
3. **Security vulnerabilities** - Critical or high severity vulnerabilities found
4. **Missing backups** - Backup system not working
5. **No rollback plan** - Rollback procedure not tested
6. **SSL certificate invalid** - Expired or self-signed certificates in production
7. **Secrets exposed** - Secrets in version control or logs
8. **No monitoring** - Monitoring and alerting not configured
9. **Resource limits not set** - Containers without resource limits
10. **Hard caps can be bypassed** - Risk engine limits can be exceeded

---

## Post-Deployment

### Post-Deployment Checklist

- [ ] All services healthy
- [ ] Health check endpoints return 200
- [ ] Metrics being collected
- [ ] Alerts firing for test conditions
- [ ] Logs flowing to aggregation
- [ ] Database backups completing
- [ ] SSL certificate valid
- [ ] Load balancer distributing traffic
- [ ] Auto-scaling responding to load
- [ ] Zero errors in Sentry
- [ ] User login working
- [ ] WebSocket connections stable
- [ ] Trade execution working (in simulation mode first)

### Monitoring First 24 Hours

- Monitor error rates every hour
- Check response times (p50, p95, p99)
- Verify no memory leaks (stable memory usage)
- Check database connection pool usage
- Monitor trade execution success rate
- Review Sentry for unexpected errors
- Check backup completion
- Verify SSL certificate renewal scheduled

---

END OF PROMPT 18

## FLOWREX BOOTSTRAP SYSTEM COMPLETE

All 19 implementation prompts (00-18) are now complete. Opus 4.5 has everything needed to rebuild the entire Flowrex trading platform from absolute zero.
