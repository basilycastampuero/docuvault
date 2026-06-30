#!/usr/bin/env bash
# Daily compressed PostgreSQL backup with 7-day retention.
#
# Usage (from the VPS host, with the repo cloned to /opt/saasvault):
#   bash scripts/backup_db.sh
#
# Add to crontab for daily automated backups:
#   0 2 * * * cd /opt/saasvault && bash scripts/backup_db.sh >> /var/log/saasvault-backup.log 2>&1
#
# Restore from a backup:
#   gunzip -c /var/backups/saasvault/saasvault_<timestamp>.sql.gz \
#     | docker compose -f docker-compose.prod.yml exec -T postgres \
#         psql -U saasvault_user saasvault_prod
#
# Make executable before use: chmod +x scripts/backup_db.sh

set -euo pipefail

# ---------------------------------------------------------------------------
# Load production credentials so the script works correctly when invoked from
# cron (which does not inherit the operator's shell environment).
# Uses the native POSTGRES_* names added in .env.production.example (Fix 2).
# ---------------------------------------------------------------------------
ENV_FILE="$(dirname "$0")/../backend/.env.production"
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck source=/dev/null
    . "$ENV_FILE"
    set +a
fi

BACKUP_DIR="/var/backups/saasvault"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/saasvault_$TIMESTAMP.sql.gz"
RETENTION_DAYS=7

mkdir -p "$BACKUP_DIR"

echo "[$(date -Iseconds)] Starting backup..."

# Write to a temp file first; only rename on success.
# This prevents a truncated/empty .sql.gz from looking like a valid backup when
# pg_dump or gzip fails mid-stream (e.g. disk full, Postgres crash).
TMP_FILE="$BACKUP_FILE.tmp"

docker compose -f "$(dirname "$0")/../docker-compose.prod.yml" exec -T postgres \
    pg_dump -U "${POSTGRES_USER:-saasvault_user}" "${POSTGRES_DB:-saasvault_prod}" \
    | gzip > "$TMP_FILE"

mv "$TMP_FILE" "$BACKUP_FILE"

echo "[$(date -Iseconds)] Backup created: $BACKUP_FILE"

# Remove backups older than the retention window
find "$BACKUP_DIR" -name "saasvault_*.sql.gz" -mtime +"$RETENTION_DAYS" -delete
echo "[$(date -Iseconds)] Cleaned up backups older than $RETENTION_DAYS days"
