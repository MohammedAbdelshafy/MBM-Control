#!/bin/bash
set -e

# ================================================================
# Clipping Factory — Cloud Deploy Script
# Deploys to a VPS with Docker. Runs 24/7 regardless of local laptop.
# ================================================================
# Prerequisites:
#   1. A VPS (e.g. $5/mo DigitalOcean droplet, Hetzner CX22, or AWS EC2)
#   2. Docker + Compose installed on the VPS
#   3. Domain (optional) pointing to the VPS IP
#
# Quick start:
#   ssh root@your-vps-ip
#   git clone https://github.com/your-org/clipping-factory.git
#   cd clipping-factory
#   cp .env.example .env   # fill in secrets
#   bash deploy/deploy.sh
# ================================================================

ENV_FILE="${1:-.env}"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: .env file not found at $ENV_FILE"
    echo "Usage: bash deploy/deploy.sh [path/to/.env]"
    exit 1
fi

echo "=== Clipping Factory Cloud Deploy ==="
echo "Using env file: $ENV_FILE"

# 1. Create docker network
echo "[1/5] Creating shared network..."
docker network inspect clipping-factory >/dev/null 2>&1 || \
    docker network create clipping-factory

# 2. Pull latest images
echo "[2/5] Pulling latest images..."
docker compose -f deploy/docker-compose.cloud.yml --env-file "$ENV_FILE" pull

# 3. Start all services
echo "[3/5] Starting services..."
docker compose -f deploy/docker-compose.cloud.yml --env-file "$ENV_FILE" up -d

# 4. Wait for API health
echo "[4/5] Waiting for API to be healthy..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/ping >/dev/null 2>&1; then
        echo "API is healthy!"
        break
    fi
    sleep 2
done

# 5. Run initial scan
echo "[5/5] Running initial campaign scan..."
curl -sf -X POST http://localhost:8000/api/v1/scan-campaigns \
    -H "Content-Type: application/json" \
    -d '{}' || echo "Initial scan queued (will run via Celery Beat)"

echo ""
echo "=== Deploy Complete ==="
echo "API:          http://localhost:8000"
echo "MinIO Console: http://localhost:9001"
echo "Flower (Celery): http://localhost:5555"
echo ""
echo "Next steps:"
echo "  1. Set up reverse proxy (Caddy/Nginx) for SSL"
echo "  2. Configure SUPABASE_WEBHOOK_URL in .env"
echo "  3. pg_cron jobs will auto-invoke Supabase Edge Functions"
echo ""
echo "Logs: docker compose -f deploy/docker-compose.cloud.yml logs -f"
