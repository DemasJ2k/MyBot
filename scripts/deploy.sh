#!/bin/bash
# ============================================================================
# Flowrex Zero-Downtime Deployment Script
# Prompt 18 - Production Deployment
#
# Usage:
#   ./deploy.sh [environment] [version]
#   ./deploy.sh staging latest
#   ./deploy.sh production v1.2.3
#
# Requirements:
#   - Docker and Docker Compose installed
#   - Access to container registry
#   - Valid SSL certificates in nginx/ssl/
# ============================================================================

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================
ENVIRONMENT="${1:-staging}"
VERSION="${2:-latest}"
REGISTRY_URL="${REGISTRY_URL:-flowrex}"
COMPOSE_FILE="docker-compose.prod.yml"
HEALTH_CHECK_URL="${HEALTH_CHECK_URL:-http://localhost:8000/health/ready}"
MAX_HEALTH_ATTEMPTS=30
HEALTH_CHECK_INTERVAL=10
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"
BACKUP_RETENTION_DAYS=30

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

send_notification() {
    local message="$1"
    local status="${2:-info}"
    
    if [ -n "$SLACK_WEBHOOK_URL" ]; then
        local emoji="📢"
        case "$status" in
            success) emoji="✅" ;;
            error) emoji="❌" ;;
            warning) emoji="⚠️" ;;
        esac
        
        curl -s -X POST "$SLACK_WEBHOOK_URL" \
            -H 'Content-Type: application/json' \
            -d "{\"text\":\"$emoji $message\"}" > /dev/null || true
    fi
}

cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Deployment failed with exit code $exit_code"
        send_notification "Flowrex $ENVIRONMENT deployment FAILED - $VERSION" "error"
    fi
}

trap cleanup EXIT

# ============================================================================
# Pre-flight Checks
# ============================================================================

preflight_checks() {
    log_info "Running pre-flight checks..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    
    # Check compose file exists
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Compose file not found: $COMPOSE_FILE"
        exit 1
    fi
    
    # Check SSL certificates for production
    if [ "$ENVIRONMENT" = "production" ]; then
        if [ ! -f "nginx/ssl/fullchain.pem" ] || [ ! -f "nginx/ssl/privkey.pem" ]; then
            log_error "SSL certificates not found in nginx/ssl/"
            log_error "Production deployment requires valid SSL certificates"
            log_info "Place fullchain.pem and privkey.pem in nginx/ssl/ directory"
            log_info "Or use: --skip-ssl-check to bypass (NOT RECOMMENDED)"
            if [ "${SKIP_SSL_CHECK:-false}" != "true" ]; then
                exit 1
            fi
            log_warning "SSL check bypassed via SKIP_SSL_CHECK=true"
        fi
    fi
    
    log_success "Pre-flight checks passed"
}

# ============================================================================
# Pre-deployment Validation
# ============================================================================

run_deployment_checklist() {
    log_info "Running deployment checklist..."
    
    if [ -f "scripts/deployment_checklist.py" ]; then
        cd backend
        if python ../scripts/deployment_checklist.py --env "$ENVIRONMENT"; then
            cd ..
            log_success "Deployment checklist passed"
        else
            cd ..
            log_error "Deployment checklist failed"
            exit 1
        fi
    else
        log_warning "Deployment checklist script not found, skipping..."
    fi
}

# ============================================================================
# Docker Image Management
# ============================================================================

pull_images() {
    log_info "Pulling Docker images..."
    
    export VERSION="$VERSION"
    export REGISTRY_URL="$REGISTRY_URL"
    
    docker pull "${REGISTRY_URL}/flowrex-backend:${VERSION}" || {
        log_warning "Could not pull backend image, will build locally"
    }
    
    docker pull "${REGISTRY_URL}/flowrex-frontend:${VERSION}" || {
        log_warning "Could not pull frontend image, will build locally"
    }
    
    log_success "Image pull complete"
}

build_images() {
    log_info "Building Docker images..."
    
    export VERSION="$VERSION"
    
    docker-compose -f "$COMPOSE_FILE" build --parallel backend frontend
    
    log_success "Image build complete"
}

# ============================================================================
# Database Operations
# ============================================================================

backup_database() {
    log_info "Creating database backup..."
    
    local backup_name="pre_deploy_$(date +%Y%m%d_%H%M%S)"
    local backup_dir="backups/postgres"
    
    mkdir -p "$backup_dir"
    
    # Check if postgres container is running
    if docker-compose -f "$COMPOSE_FILE" ps postgres | grep -q "Up"; then
        docker-compose -f "$COMPOSE_FILE" exec -T postgres \
            pg_dump -U "${POSTGRES_USER:-flowrex}" "${POSTGRES_DB:-flowrex}" \
            > "${backup_dir}/${backup_name}.sql"
        
        # Compress backup
        gzip "${backup_dir}/${backup_name}.sql"
        
        log_success "Database backup created: ${backup_name}.sql.gz"
        
        # Cleanup old backups
        find "$backup_dir" -name "*.sql.gz" -mtime +$BACKUP_RETENTION_DAYS -delete
    else
        log_warning "PostgreSQL not running, skipping backup"
    fi
}

run_migrations() {
    log_info "Running database migrations..."
    
    if [ -f "backend/scripts/migrate.py" ]; then
        cd backend
        python scripts/migrate.py || {
            cd ..
            log_error "Migration failed"
            exit 1
        }
        cd ..
        log_success "Migrations complete"
    else
        log_warning "Migration script not found, skipping..."
    fi
}

# ============================================================================
# Service Deployment
# ============================================================================

deploy_backend() {
    log_info "Deploying backend services..."
    
    export VERSION="$VERSION"
    export REGISTRY_URL="$REGISTRY_URL"
    export ENVIRONMENT="$ENVIRONMENT"
    
    # Get current replica count
    local current_replicas
    current_replicas=$(docker-compose -f "$COMPOSE_FILE" ps -q backend 2>/dev/null | wc -l)
    current_replicas=${current_replicas:-0}
    
    if [ "$current_replicas" -eq 0 ]; then
        # Fresh deployment
        docker-compose -f "$COMPOSE_FILE" up -d backend
    else
        # Rolling update - add new container first
        docker-compose -f "$COMPOSE_FILE" up -d --scale backend=$((current_replicas + 1)) --no-recreate backend
        
        # Wait for new container to be healthy
        log_info "Waiting for new backend container to be healthy..."
        sleep 30
        
        # Health check
        local healthy=false
        for i in $(seq 1 $MAX_HEALTH_ATTEMPTS); do
            if curl -sf "$HEALTH_CHECK_URL" > /dev/null 2>&1; then
                healthy=true
                break
            fi
            log_info "Health check attempt $i/$MAX_HEALTH_ATTEMPTS..."
            sleep $HEALTH_CHECK_INTERVAL
        done
        
        if [ "$healthy" = false ]; then
            log_error "Backend health check failed"
            # Rollback
            docker-compose -f "$COMPOSE_FILE" up -d --scale backend="$current_replicas" --no-recreate backend
            exit 1
        fi
        
        # Remove old containers and scale to desired count
        docker-compose -f "$COMPOSE_FILE" up -d --scale backend="${BACKEND_REPLICAS:-5}" backend
    fi
    
    log_success "Backend deployment complete"
}

deploy_frontend() {
    log_info "Deploying frontend services..."
    
    export VERSION="$VERSION"
    export REGISTRY_URL="$REGISTRY_URL"
    
    docker-compose -f "$COMPOSE_FILE" up -d frontend
    
    # Wait for frontend to be ready
    sleep 20
    
    log_success "Frontend deployment complete"
}

deploy_infrastructure() {
    log_info "Deploying infrastructure services..."
    
    # Start core infrastructure
    docker-compose -f "$COMPOSE_FILE" up -d postgres redis
    
    # Wait for database to be ready
    log_info "Waiting for database..."
    local db_ready=false
    for i in $(seq 1 30); do
        if docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U "${POSTGRES_USER:-flowrex}" > /dev/null 2>&1; then
            db_ready=true
            break
        fi
        sleep 2
    done
    
    if [ "$db_ready" = false ]; then
        log_error "Database failed to start"
        exit 1
    fi
    
    # Start monitoring stack
    docker-compose -f "$COMPOSE_FILE" up -d prometheus grafana node-exporter redis-exporter postgres-exporter
    
    # Start NGINX
    docker-compose -f "$COMPOSE_FILE" up -d nginx
    
    log_success "Infrastructure deployment complete"
}

# ============================================================================
# Post-deployment Validation
# ============================================================================

validate_deployment() {
    log_info "Validating deployment..."
    
    local all_healthy=true
    local endpoints=(
        "http://localhost:8000/health"
        "http://localhost:8000/health/ready"
        "http://localhost:3000/api/health"
    )
    
    for endpoint in "${endpoints[@]}"; do
        log_info "Checking $endpoint..."
        if curl -sf "$endpoint" > /dev/null 2>&1; then
            log_success "$endpoint is healthy"
        else
            log_error "$endpoint is not responding"
            all_healthy=false
        fi
    done
    
    if [ "$all_healthy" = false ]; then
        log_error "Post-deployment validation failed"
        return 1
    fi
    
    log_success "All endpoints healthy"
    return 0
}

# ============================================================================
# Main Deployment Flow
# ============================================================================

main() {
    echo ""
    echo "========================================================"
    echo "  FLOWREX DEPLOYMENT"
    echo "========================================================"
    echo "  Environment: $ENVIRONMENT"
    echo "  Version:     $VERSION"
    echo "  Registry:    $REGISTRY_URL"
    echo "  Timestamp:   $(date)"
    echo "========================================================"
    echo ""
    
    send_notification "Starting Flowrex $ENVIRONMENT deployment - $VERSION" "info"
    
    # Step 1: Pre-flight checks
    log_info "[1/9] Pre-flight checks..."
    preflight_checks
    
    # Step 2: Deployment checklist
    log_info "[2/9] Running deployment checklist..."
    run_deployment_checklist
    
    # Step 3: Pull/build images
    log_info "[3/9] Preparing Docker images..."
    pull_images
    
    # Step 4: Deploy infrastructure
    log_info "[4/9] Deploying infrastructure..."
    deploy_infrastructure
    
    # Step 5: Backup database
    log_info "[5/9] Creating database backup..."
    backup_database
    
    # Step 6: Run migrations
    log_info "[6/9] Running database migrations..."
    run_migrations
    
    # Step 7: Deploy backend
    log_info "[7/9] Deploying backend..."
    deploy_backend
    
    # Step 8: Deploy frontend
    log_info "[8/9] Deploying frontend..."
    deploy_frontend
    
    # Step 9: Validate deployment
    log_info "[9/9] Validating deployment..."
    if validate_deployment; then
        echo ""
        echo "========================================================"
        echo -e "  ${GREEN}✅ DEPLOYMENT SUCCESSFUL${NC}"
        echo "========================================================"
        echo "  Environment: $ENVIRONMENT"
        echo "  Version:     $VERSION"
        echo "  Timestamp:   $(date)"
        echo ""
        echo "  Services:"
        echo "    - Backend:    http://localhost:8000"
        echo "    - Frontend:   http://localhost:3000"
        echo "    - Prometheus: http://localhost:9090"
        echo "    - Grafana:    http://localhost:3001"
        echo "========================================================"
        echo ""
        
        send_notification "Flowrex $ENVIRONMENT deployment SUCCESSFUL - $VERSION" "success"
    else
        echo ""
        echo "========================================================"
        echo -e "  ${RED}❌ DEPLOYMENT VALIDATION FAILED${NC}"
        echo "========================================================"
        echo "  Consider rolling back to the previous version."
        echo "  Run: ./scripts/rollback.sh <previous_version>"
        echo "========================================================"
        echo ""
        exit 1
    fi
}

# Run main function
main "$@"
