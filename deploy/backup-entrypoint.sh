#!/usr/bin/env bash
# Scheduler/runner for the backup container. Works in two modes:
#
#   * Compose (default): long-running loop — backs up once on boot, then daily
#     at BACKUP_HOUR. Used by deploy/docker-compose.prod.yml.
#   * Railway cron (BACKUP_RUN_ONCE=1): run a single backup and exit. Railway's
#     cron schedule re-invokes the container; it must not loop.
#
# backup.sh pushes to Google Drive via rclone when RCLONE_REMOTE is set. On a
# headless platform with no persistent ~/.config, provide the rclone config as
# a base64 secret in RCLONE_CONF_BASE64 and it's materialized here.
set -euo pipefail

BACKUP_HOUR="${BACKUP_HOUR:-2}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"

# Materialize rclone config from a secret (Railway/headless) if provided.
if [ -n "${RCLONE_CONF_BASE64:-}" ]; then
  mkdir -p /root/.config/rclone
  echo "$RCLONE_CONF_BASE64" | base64 -d > /root/.config/rclone/rclone.conf
  echo "[backup-loop] wrote rclone.conf from RCLONE_CONF_BASE64"
fi

run_backup() {
  echo "[backup-loop] $(date '+%F %T %Z') — running backup"
  if /usr/local/bin/backup.sh "$BACKUP_DIR"; then
    echo "[backup-loop] backup OK"
  else
    echo "[backup-loop] backup FAILED (exit $?)" >&2
    return 1
  fi
}

# One-shot mode (Railway cron / manual run).
if [ "${BACKUP_RUN_ONCE:-0}" = "1" ]; then
  run_backup
  exit $?
fi

seconds_until_hour() {
  local target="$1" now_h now_m now_s now_total target_total
  now_h=$(date +%-H); now_m=$(date +%-M); now_s=$(date +%-S)
  now_total=$(( now_h * 3600 + now_m * 60 + now_s ))
  target_total=$(( target * 3600 ))
  if (( target_total <= now_total )); then
    target_total=$(( target_total + 86400 ))
  fi
  echo $(( target_total - now_total ))
}

echo "[backup-loop] starting — daily at ${BACKUP_HOUR}:00 ${TZ:-UTC}, dir=$BACKUP_DIR, remote=${RCLONE_REMOTE:-<none>}"
run_backup || true   # baseline on boot; don't crash the loop if first run fails

while true; do
  sleep_for=$(seconds_until_hour "$BACKUP_HOUR")
  echo "[backup-loop] sleeping ${sleep_for}s until next ${BACKUP_HOUR}:00"
  sleep "$sleep_for"
  run_backup || true
done
