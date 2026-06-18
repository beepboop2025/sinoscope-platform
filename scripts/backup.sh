#!/usr/bin/env bash
# EconScraper / PALIMPSEST backup script.
# Usage: ./scripts/backup.sh [output_dir]
#
# Backs up PostgreSQL (pg_dump) + the app data/ snapshots, then — when
# RCLONE_REMOTE is set — pushes the archives to Google Drive via rclone.
# Designed for cron or the in-stack `backup` service (deploy/docker-compose.prod.yml).
#
# Environment:
#   DATABASE_URL          postgres connection string (required for the DB dump)
#   RCLONE_REMOTE         e.g. "gdrive:PALIMPSEST/backups" — if unset, push is skipped
#   LOCAL_RETENTION_DAYS  delete local archives older than N days (default 7)
#   REMOTE_RETENTION_DAYS prune remote archives older than N days (default 30)
#   BACKUP_INCLUDE_MINIO  if "1", also sync the MinIO raw data dir to the remote
#   MINIO_DATA_DIR        path to MinIO data when BACKUP_INCLUDE_MINIO=1 (default /minio-data)
#   APP_DATA_DIR          path to app data/ snapshots (default ./data, container: /app/data)

set -euo pipefail

BACKUP_DIR="${1:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_URL="${DATABASE_URL:-postgresql://localhost:5432/econscraper}"
RCLONE_REMOTE="${RCLONE_REMOTE:-}"
LOCAL_RETENTION_DAYS="${LOCAL_RETENTION_DAYS:-7}"
REMOTE_RETENTION_DAYS="${REMOTE_RETENTION_DAYS:-30}"
APP_DATA_DIR="${APP_DATA_DIR:-./data}"

mkdir -p "$BACKUP_DIR"
echo "[backup] Starting backup at $TIMESTAMP"

# ── 1. PostgreSQL dump ───────────────────────────────────────────
DB_FILE="$BACKUP_DIR/econscraper_db_${TIMESTAMP}.sql.gz"
echo "[backup] Dumping PostgreSQL..."
pg_dump "$DB_URL" | gzip > "$DB_FILE"
echo "[backup] DB backup: $DB_FILE ($(du -h "$DB_FILE" | cut -f1))"

# ── 2. App data/ snapshots (CBB / DDTI time-series, raw metadata) ─
if [ -d "$APP_DATA_DIR" ]; then
  DATA_FILE="$BACKUP_DIR/app_data_${TIMESTAMP}.tar.gz"
  echo "[backup] Archiving $APP_DATA_DIR ..."
  tar -czf "$DATA_FILE" -C "$(dirname "$APP_DATA_DIR")" "$(basename "$APP_DATA_DIR")" 2>/dev/null || true
  [ -f "$DATA_FILE" ] && echo "[backup] Data archive: $DATA_FILE ($(du -h "$DATA_FILE" | cut -f1))"
fi

# ── 3. Push to Google Drive via rclone ───────────────────────────
if [ -n "$RCLONE_REMOTE" ] && command -v rclone &> /dev/null; then
  echo "[backup] Pushing archives to $RCLONE_REMOTE ..."
  rclone copy "$BACKUP_DIR" "$RCLONE_REMOTE" \
    --include "econscraper_db_*.sql.gz" \
    --include "app_data_*.tar.gz" \
    --transfers 4 --checkers 8 --quiet
  echo "[backup] rclone copy complete."

  # Optional: mirror the (potentially large) MinIO raw object store.
  if [ "${BACKUP_INCLUDE_MINIO:-0}" = "1" ]; then
    MINIO_DATA_DIR="${MINIO_DATA_DIR:-/minio-data}"
    if [ -d "$MINIO_DATA_DIR" ]; then
      echo "[backup] Syncing MinIO raw data → $RCLONE_REMOTE/minio-raw ..."
      rclone sync "$MINIO_DATA_DIR" "$RCLONE_REMOTE/minio-raw" --transfers 4 --checkers 8 --quiet
    fi
  fi

  # Prune old archives on the remote.
  rclone delete "$RCLONE_REMOTE" --min-age "${REMOTE_RETENTION_DAYS}d" \
    --include "econscraper_db_*.sql.gz" --include "app_data_*.tar.gz" --quiet 2>/dev/null || true
elif [ -n "$RCLONE_REMOTE" ]; then
  echo "[backup] WARNING: RCLONE_REMOTE set but rclone not installed — skipping cloud push." >&2
else
  echo "[backup] RCLONE_REMOTE not set — local backup only."
fi

# ── 4. Local retention ───────────────────────────────────────────
find "$BACKUP_DIR" -name "econscraper_db_*.sql.gz" -mtime +"$LOCAL_RETENTION_DAYS" -delete 2>/dev/null || true
find "$BACKUP_DIR" -name "app_data_*.tar.gz"      -mtime +"$LOCAL_RETENTION_DAYS" -delete 2>/dev/null || true

echo "[backup] Done."
