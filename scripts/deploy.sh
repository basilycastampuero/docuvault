#!/usr/bin/env bash
# Idempotent production deploy script.
#
# Prerequisites on the VPS:
#   - Docker + Docker Compose plugin installed
#   - openssl available (for certificate generation)
#   - Repo cloned to /opt/saasvault (or another path)
#   - backend/.env.production populated (copy from backend/.env.production.example)
#
# Usage (from the repo root on the VPS):
#   bash scripts/deploy.sh
#
# Make executable before use: chmod +x scripts/deploy.sh

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

echo "==> Pulling latest code from main..."
git pull origin main

echo "==> Generating self-signed certificate (if missing)..."
CERTS_DIR="nginx/certs"
mkdir -p "$CERTS_DIR"
if [ ! -f "$CERTS_DIR/selfsigned.crt" ]; then
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$CERTS_DIR/selfsigned.key" \
        -out "$CERTS_DIR/selfsigned.crt" \
        -subj "/C=US/ST=State/L=City/O=SasVault/CN=localhost"
    echo "Self-signed certificate generated at $CERTS_DIR/"
else
    echo "Certificate already exists, skipping generation."
fi

echo "==> Building Docker images..."
docker compose -f docker-compose.prod.yml build

echo "==> Starting all services..."
# The 'migrate' service runs automatically before web/worker/beat because those
# services declare `depends_on: migrate: condition: service_completed_successfully`.
# Running it explicitly here as well would apply migrations twice — removed.
docker compose -f docker-compose.prod.yml up -d

echo "==> Pruning unused Docker images..."
docker image prune -f

echo "==> Deploy complete. Services running:"
docker compose -f docker-compose.prod.yml ps
