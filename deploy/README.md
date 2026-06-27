# Production Deployment — Digital Ocean VPS

## Prerequisites

- **VPS**: Ubuntu 24.04 LTS, 4GB RAM, 2 vCPUs minimum
- **Domain**: DNS A record pointing to the VPS IP
- **Docker**: Docker Engine + Docker Compose v2

### Install Docker on Ubuntu

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in
```

## Quick Start

```bash
# 1. Clone the repo on the VPS
git clone https://github.com/vireshsoedhwa/market-data-api.git /opt/market-data-api
cd /opt/market-data-api

# 2. Run setup (configures firewall, creates .env.prod from template)
./deploy/deploy.sh setup

# 3. Edit .env.prod with real credentials
nano .env.prod

# 4. Deploy
./deploy/deploy.sh deploy
```

## Generating Strong Secrets

```bash
# Postgres/Redis password (32 chars)
openssl rand -base64 32

# API key (64 chars)
openssl rand -hex 32
```

## Commands

| Command | Description |
|---------|-------------|
| `./deploy/deploy.sh setup` | First-time setup: firewall + env template |
| `./deploy/deploy.sh deploy` | Build + start all services |
| `./deploy/deploy.sh status` | Check service health |
| `./deploy/deploy.sh logs [service]` | Tail logs |
| `./deploy/deploy.sh backup` | Manual DB backup |
| `./deploy/deploy.sh stop` | Stop everything |
| `./deploy/deploy.sh update` | Git pull + redeploy |

## Architecture (Production)

```
Internet
   │
   ▼ (port 443, TLS)
┌──────────┐
│  Caddy   │ ← Auto TLS via Let's Encrypt
└────┬─────┘
     │ (port 8010, internal)
┌────▼─────────────────────────────┐
│      market-data-api (FastAPI)   │
│      4 uvicorn workers           │
└────┬──────────────┬──────────────┘
     │              │
┌────▼────┐   ┌────▼────┐
│   DB    │   │  Redis  │  ← Not exposed to internet
│(pg:5432)│   │ (:6379) │
└─────────┘   └─────────┘
```

## Backups

- **Automated**: Daily pg_dump via `db-backup` service
- **Retention**: 7 daily, 4 weekly, 6 monthly
- **Location**: `db_backups` Docker volume

To copy backups off the VPS:
```bash
docker cp $(docker compose -f docker-compose.prod.yml ps -q db-backup):/backups ./local-backups/
```

## Monitoring

Health endpoint (no auth required):
```bash
curl https://api.mergemind.ca/health
```

Check all services:
```bash
./deploy/deploy.sh status
```

## Security Notes

- Only ports 22 (SSH), 80, 443 are open via UFW
- DB and Redis are on internal Docker network only
- Redis requires password + has memory limit
- API runs as non-root user in container
- TLS is auto-managed by Caddy (Let's Encrypt)
- All API endpoints (except /health) require Bearer token auth
