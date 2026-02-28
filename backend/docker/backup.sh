#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# DragonScope PostgreSQL Backup Script
#
# Performs automated pg_dump backups and cleans up old files.
# Designed to run inside the postgres container or a sidecar with
# access to the database.
#
# Usage:
#   docker compose exec postgres /backups/backup.sh
#   # Or via cron on the host:
#   docker compose -f docker-compose.prod.yml exec -T postgres /backups/backup.sh
#
# Make executable: chmod +x docker/backup.sh
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
PG_USER="${POSTGRES_USER:-dragonscope}"
PG_DB="${POSTGRES_DB:-dragonscope}"
PG_HOST="${POSTGRES_HOST:-localhost}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/dragonscope_${TIMESTAMP}.dump"

# Ensure backup directory exists
mkdir -p "${BACKUP_DIR}"

echo "[$(date -Iseconds)] Starting PostgreSQL backup..."
echo "[$(date -Iseconds)] Database: ${PG_DB} | User: ${PG_USER} | Host: ${PG_HOST}"

# Run pg_dump with custom format (compressed, supports parallel restore)
pg_dump \
    --host="${PG_HOST}" \
    --username="${PG_USER}" \
    --dbname="${PG_DB}" \
    --format=custom \
    --compress=6 \
    --verbose \
    --file="${BACKUP_FILE}" \
    2>&1

BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "[$(date -Iseconds)] Backup complete: ${BACKUP_FILE} (${BACKUP_SIZE})"

# Delete backups older than retention period
echo "[$(date -Iseconds)] Cleaning up backups older than ${RETENTION_DAYS} days..."
DELETED_COUNT=$(find "${BACKUP_DIR}" -name "dragonscope_*.dump" -type f -mtime +${RETENTION_DAYS} -print -delete | wc -l)
echo "[$(date -Iseconds)] Deleted ${DELETED_COUNT} old backup(s)"

# List current backups
echo "[$(date -Iseconds)] Current backups:"
ls -lh "${BACKUP_DIR}"/dragonscope_*.dump 2>/dev/null || echo "  (none)"

echo "[$(date -Iseconds)] Backup job finished successfully"
