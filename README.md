# Market Data API

Standalone market data acquisition, normalization, and caching service. Built with FastAPI, Celery, TimescaleDB, and Redis.

## Services

| Service | Description |
|---------|-------------|
| **market-data-api** | FastAPI REST API (port 8010) |
| **market-data-worker** | Celery background worker for data fetching |
| **db** | TimescaleDB (PostgreSQL 16) |
| **redis** | Redis 7 (caching + Celery broker) |
| **caddy** | Reverse proxy with automatic TLS |
| **db-backup** | Automated daily PostgreSQL backups |

## Deploying to Digital Ocean VPS

### Prerequisites

- VPS with Docker Engine + Docker Compose v2
- DNS A record pointing to the VPS IP
- GitHub PAT with `read:packages` scope (to pull images from GHCR)

### Step-by-step

```bash
# 1. Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in

# 2. Clone the repo
git clone https://github.com/vireshsoedhwa/market-data-api.git /opt/market-data-api
cd /opt/market-data-api

# 3. Authenticate to GitHub Container Registry
echo "YOUR_GITHUB_PAT" | docker login ghcr.io -u vireshsoedhwa --password-stdin

# 4. Open firewall ports
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp

# 5. Run setup (creates .env.prod from template)
./deploy/deploy.sh setup

# 6. Edit .env.prod with real credentials
nano .env.prod
#   - Set DOMAIN=api.mergemind.ca (or DOMAIN=http://localhost for testing without TLS)
#   - Set IMAGE_TAG to the desired commit hash
#   - Generate and fill POSTGRES_PASSWORD, REDIS_PASSWORD, MARKET_DATA_INTERNAL_API_KEY
#   - Add provider API keys

# 7. Deploy
./deploy/deploy.sh deploy

# 8. Verify
curl https://api.mergemind.ca/health
```

### Generating Secrets

```bash
openssl rand -base64 32   # for POSTGRES_PASSWORD and REDIS_PASSWORD
openssl rand -hex 32      # for MARKET_DATA_INTERNAL_API_KEY
```

### Deploy Commands

| Command | Description |
|---------|-------------|
| `./deploy/deploy.sh setup` | First-time setup: firewall + env template |
| `./deploy/deploy.sh deploy` | Pull images + start all services |
| `./deploy/deploy.sh status` | Check service health |
| `./deploy/deploy.sh logs [service]` | Tail logs (e.g. `logs market-data-api`) |
| `./deploy/deploy.sh backup` | Manual DB backup |
| `./deploy/deploy.sh stop` | Stop everything |
| `./deploy/deploy.sh update` | Git pull + redeploy |

### Redeploying with a New Image Tag

```bash
# Update IMAGE_TAG in .env.prod
sed -i 's/IMAGE_TAG=.*/IMAGE_TAG=<new-commit-hash>/' .env.prod

# Redeploy
./deploy/deploy.sh deploy
```

### Architecture

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
└────┬──────────────┬──────────────┘
     │              │
┌────▼────┐   ┌────▼────┐
│   DB    │   │  Redis  │  ← Not exposed to internet
│(pg:5432)│   │ (:6379) │
└─────────┘   └─────────┘
```

### Security

- Only ports 22 (SSH), 80, 443 open via UFW
- DB and Redis on internal Docker network only
- TLS auto-managed by Caddy (Let's Encrypt)
- All API endpoints (except `/health`) require Bearer token auth

See [deploy/README.md](deploy/README.md) for more details.