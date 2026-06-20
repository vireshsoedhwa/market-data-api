#!/usr/bin/env bash
# =============================================================================
# Production Deployment Script for Digital Ocean VPS
#
# Usage:
#   ./deploy/deploy.sh [setup|deploy|status|logs|backup]
#
# Prerequisites:
#   - Ubuntu 24.04 VPS with SSH access
#   - Docker and Docker Compose installed
#   - .env.prod file configured (see deploy/.env.prod.example)
# =============================================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.prod.yml"
ENV_FILE="$PROJECT_DIR/.env.prod"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[deploy]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
err()  { echo -e "${RED}[error]${NC} $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

cmd_setup() {
    log "Setting up production environment on this host..."

    # Check Docker
    if ! command -v docker &>/dev/null; then
        err "Docker is not installed. Install with: curl -fsSL https://get.docker.com | sh"
    fi

    # Check .env.prod
    if [[ ! -f "$ENV_FILE" ]]; then
        warn ".env.prod not found. Creating from template..."
        cp "$PROJECT_DIR/deploy/.env.prod.example" "$ENV_FILE"
        warn "Edit $ENV_FILE with real credentials before deploying."
        return
    fi

    # Validate required vars
    local required_vars=("POSTGRES_PASSWORD" "REDIS_PASSWORD" "MARKET_DATA_INTERNAL_API_KEY" "DOMAIN")
    for var in "${required_vars[@]}"; do
        if ! grep -q "^${var}=" "$ENV_FILE" || grep -q "CHANGE_ME" "$ENV_FILE"; then
            warn "$var is not configured in .env.prod"
        fi
    done

    # Setup firewall
    if command -v ufw &>/dev/null; then
        log "Configuring UFW firewall..."
        sudo ufw default deny incoming
        sudo ufw default allow outgoing
        sudo ufw allow 22/tcp    # SSH
        sudo ufw allow 80/tcp    # HTTP (Caddy redirect)
        sudo ufw allow 443/tcp   # HTTPS
        sudo ufw allow 443/udp   # HTTP/3
        sudo ufw --force enable
        log "Firewall configured: SSH(22), HTTP(80), HTTPS(443) only."
    else
        warn "UFW not found. Configure firewall manually."
    fi

    log "Setup complete. Run './deploy/deploy.sh deploy' to start services."
}

cmd_deploy() {
    log "Deploying production stack..."

    if [[ ! -f "$ENV_FILE" ]]; then
        err ".env.prod not found. Run './deploy/deploy.sh setup' first."
    fi

    # Build and start
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build --no-cache
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d

    log "Waiting for services to be healthy..."
    sleep 10

    # Check health
    if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps | grep -q "unhealthy"; then
        warn "Some services are unhealthy:"
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
    else
        log "All services running."
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
    fi

    log "Deployment complete."
}

cmd_status() {
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
}

cmd_logs() {
    local service="${1:-}"
    if [[ -n "$service" ]]; then
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" logs -f "$service"
    else
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" logs -f
    fi
}

cmd_backup() {
    log "Triggering manual database backup..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec db-backup /backup.sh
    log "Backup complete. Files stored in db_backups volume."
}

cmd_stop() {
    log "Stopping all services..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down
    log "Stopped."
}

cmd_update() {
    log "Pulling latest code and redeploying..."
    cd "$PROJECT_DIR"
    git pull origin main
    cmd_deploy
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

case "${1:-help}" in
    setup)  cmd_setup ;;
    deploy) cmd_deploy ;;
    status) cmd_status ;;
    logs)   cmd_logs "${2:-}" ;;
    backup) cmd_backup ;;
    stop)   cmd_stop ;;
    update) cmd_update ;;
    *)
        echo "Usage: $0 {setup|deploy|status|logs|backup|stop|update}"
        echo ""
        echo "Commands:"
        echo "  setup   - Configure firewall, validate .env.prod"
        echo "  deploy  - Build and start all services"
        echo "  status  - Show service status"
        echo "  logs    - Tail logs (optionally for a specific service)"
        echo "  backup  - Trigger manual DB backup"
        echo "  stop    - Stop all services"
        echo "  update  - Git pull + redeploy"
        exit 1
        ;;
esac
