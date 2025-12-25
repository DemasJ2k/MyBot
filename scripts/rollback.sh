#!/bin/bash
# ============================================================================
# Flowrex Rollback Script
# Prompt 18 - Production Deployment
#
# Usage:
#   ./rollback.sh <version> [backup_name]
#   ./rollback.sh v1.2.2
#   ./rollback.sh v1.2.2 pre_deploy_20251225_120000
#
# This script performs:
#   1. Optional database restore from backup
#   2. Service rollback to specified version
#   3. Health verification
# ============================================================================

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================
TARGET_VERSION="${1:-}"
BACKUP_NAME="${2:-}"
COMPOSE_FILE="docker-compose.prod.yml"
REGISTRY_URL="${REGISTRY_URL:-flowrex}"
HEALTH_CHECK_URL="${HEALTH_CHECK_URL:-http://localhost:8000/health/ready}"
MAX_HEALTH_ATTEMPTS=30
HEALTH_CHECK_INTERVAL=10
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"

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
            rollback) emoji="🔄" ;;
        esac
        
        curl -s -X POST "$SLACK_WEBHOOK_URL" \
            -H 'Content-Type: application/json' \
            -d "{\"text\":\"$emoji $message\"}" > /dev/null || true
    fi
}

show_usage() {
    echo "Usage: $0 <version> [backup_name]"
    echo ""
    echo "Arguments:"
    echo "  version      Required. Docker image version to rollback to (e.g., v1.2.2)"
    echo "  backup_name  Optional. Database backup to restore (e.g., pre_deploy_20251225_120000)"
    echo ""
    echo "Examples:"
    echo "  $0 v1.2.2                              # Rollback services only"
    echo "  $0 v1.2.2 pre_deploy_20251225_120000   # Rollback with database restore"
    echo ""
    echo "Available backups:"
    ls -la backups/postgres/*.sql.gz 2>/dev/null || echo "  No backups found"
}

confirm_action() {
    local prompt="$1"
    echo -e "${YELLOW}$prompt${NC}"
    read -p "Type 'YES' to confirm: " response
    if [ "$response" != "YES" ]; then
        log_error "Rollback cancelled"
        exit 1
    fi
}

# ============================================================================
# Validation
# ============================================================================

validate_inputs() {
    if [ -z "$TARGET_VERSION" ]; then
        log_error "Version argument is required"
        echo ""
        show_usage
        exit 1
    fi
    
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Compose file not found: $COMPOSE_FILE"
        exit 1
    fi
    
    if [ -n "$BACKUP_NAME" ]; then
        local backup_path="backups/postgres/${BACKUP_NAME}.sql.gz"
        if [ ! -f "$backup_path" ]; then
            log_error "Backup file not found: $backup_path"
            echo ""
            echo "Available backups:"
            ls -la backups/postgres/*.sql.gz 2>/dev/null || echo "  No backups found"
            exit 1
        fi
    fi
}

# ============================================================================
# Database Restore
# ============================================================================

restore_database() {
    local backup_name="$1"
    local backup_path="backups/postgres/${backup_name}.sql.gz"
    
    log_info "Restoring database from $backup_name..."
    
    # Confirm database restore
    confirm_action "This will restore the database from backup. All data since the backup will be lost!"
    
    # Check if postgres is running
    if ! docker-compose -f "$COMPOSE_FILE" ps postgres | grep -q "Up"; then
        log_error "PostgreSQL is not running"
        exit 1
    fi
    
    # Stop backend to prevent connections during restore
    log_info "Stopping backend services..."
    docker-compose -f "$COMPOSE_FILE" stop backend
    
    # Wait for connections to close
    sleep 5
    
    # Terminate remaining connections
    docker-compose -f "$COMPOSE_FILE" exec -T postgres psql -U "${POSTGRES_USER:-flowrex}" -d postgres -c \
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${POSTGRES_DB:-flowrex}' AND pid <> pg_backend_pid();" \
        > /dev/null 2>&1 || true
    
    # Drop and recreate database
    log_info "Recreating database..."
    docker-compose -f "$COMPOSE_FILE" exec -T postgres psql -U "${POSTGRES_USER:-flowrex}" -d postgres -c \
        "DROP DATABASE IF EXISTS ${POSTGRES_DB:-flowrex};"
    docker-compose -f "$COMPOSE_FILE" exec -T postgres psql -U "${POSTGRES_USER:-flowrex}" -d postgres -c \
        "CREATE DATABASE ${POSTGRES_DB:-flowrex};"
    
    # Restore from backup
    log_info "Restoring data..."
    gunzip -c "$backup_path" | docker-compose -f "$COMPOSE_FILE" exec -T postgres \
        psql -U "${POSTGRES_USER:-flowrex}" -d "${POSTGRES_DB:-flowrex}"
    
    log_success "Database restored from $backup_name"
}

# ============================================================================
# Service Rollback
# ============================================================================

rollback_services() {
    local version="$1"
    
    log_info "Rolling back services to version $version..."
    
    export VERSION="$version"
    export REGISTRY_URL="$REGISTRY_URL"
    
    # Pull the target version images
    log_info "Pulling images for version $version..."
    docker pull "${REGISTRY_URL}/flowrex-backend:${version}" || {
        log_error "Failed to pull backend image for version $version"
        exit 1
    }
    docker pull "${REGISTRY_URL}/flowrex-frontend:${version}" || {
        log_error "Failed to pull frontend image for version $version"
        exit 1
    }
    
    # Deploy the previous version
    log_info "Deploying version $version..."
    docker-compose -f "$COMPOSE_FILE" up -d backend frontend
    
    # Wait for services to start
    sleep 30
    
    log_success "Services rolled back to version $version"
}

# ============================================================================
# Health Verification
# ============================================================================

verify_health() {
    log_info "Verifying service health..."
    
    local healthy=false
    for i in $(seq 1 $MAX_HEALTH_ATTEMPTS); do
        if curl -sf "$HEALTH_CHECK_URL" > /dev/null 2>&1; then
            healthy=true
            break
        fi
        log_info "Health check attempt $i/$MAX_HEALTH_ATTEMPTS..."
        sleep $HEALTH_CHECK_INTERVAL
    done
    
    if [ "$healthy" = true ]; then
        log_success "Services are healthy"
        return 0
    else
        log_error "Services failed health check after rollback"
        return 1
    fi
}

# ============================================================================
# Rollback Migrations (Optional)
# ============================================================================

rollback_migrations() {
    log_info "Checking for migration rollback..."
    
    if [ -f "backend/scripts/rollback.py" ]; then
        read -p "Do you want to rollback database migrations? (y/N): " response
        if [ "$response" = "y" ] || [ "$response" = "Y" ]; then
            cd backend
            python scripts/rollback.py --steps 1
            cd ..
            log_success "Migration rolled back"
        fi
    fi
}

# ============================================================================
# Main Rollback Flow
# ============================================================================

main() {
    echo ""
    echo "========================================================"
    echo "  FLOWREX ROLLBACK"
    echo "========================================================"
    echo "  Target Version: ${TARGET_VERSION:-'Not specified'}"
    echo "  Database Backup: ${BACKUP_NAME:-'None (service rollback only)'}"
    echo "  Timestamp: $(date)"
    echo "========================================================"
    echo ""
    
    # Validate inputs
    validate_inputs
    
    # Confirm rollback
    echo -e "${RED}⚠️  WARNING: This will rollback production services!${NC}"
    echo ""
    confirm_action "Are you sure you want to proceed with the rollback?"
    
    send_notification "Starting Flowrex rollback to $TARGET_VERSION" "rollback"
    
    # Step 1: Database restore (if backup specified)
    if [ -n "$BACKUP_NAME" ]; then
        log_info "[1/3] Restoring database..."
        restore_database "$BACKUP_NAME"
    else
        log_info "[1/3] Skipping database restore (no backup specified)"
    fi
    
    # Step 2: Service rollback
    log_info "[2/3] Rolling back services..."
    rollback_services "$TARGET_VERSION"
    
    # Step 3: Health verification
    log_info "[3/3] Verifying health..."
    if verify_health; then
        echo ""
        echo "========================================================"
        echo -e "  ${GREEN}✅ ROLLBACK SUCCESSFUL${NC}"
        echo "========================================================"
        echo "  Version: $TARGET_VERSION"
        echo "  Database: ${BACKUP_NAME:-'Not restored'}"
        echo "  Timestamp: $(date)"
        echo "========================================================"
        echo ""
        
        send_notification "Flowrex rollback to $TARGET_VERSION SUCCESSFUL" "success"
    else
        echo ""
        echo "========================================================"
        echo -e "  ${RED}❌ ROLLBACK VERIFICATION FAILED${NC}"
        echo "========================================================"
        echo "  Manual intervention may be required."
        echo "  Check logs: docker-compose -f $COMPOSE_FILE logs"
        echo "========================================================"
        echo ""
        
        send_notification "Flowrex rollback to $TARGET_VERSION FAILED - manual intervention required" "error"
        exit 1
    fi
}

# Check for help flag
if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    show_usage
    exit 0
fi

# Run main function
main "$@"
