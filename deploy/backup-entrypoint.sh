#!/usr/bin/env bash
# Long-running scheduler for the backup container.
# Sleeps until BACKUP_HOUR each day, runs backup.sh (which pushes to Google
# Drive via rclone when RCLONE_REMOTE is set), then repeats. Runs one backup
# immediately on first boot so a fresh deploy has a baseline snapshot.
set -euo pipefail

BACKUP_HOUR="${BACKUP_HOUR:-2}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"

run_backup() {
  echo "[backup-loop] $(date '+%F %T %Z') — running backup"
  if /usr/local/bin/backup.sh "$BACKUP_DIR"; then
    echo "[backup-loop] backup OK"
  else
    echo "[backup-loop] backup FAILED (exit $?) — will retry next cycle" >&2
  fi
}

seconds_until_hour() {
  # Seconds from now until the next occurrence of $1:00 local time.
  local target="$1" now_h now_m now_s now_total target_total
  now_h=$(date +%-H); now_m=$(date +%-M); now_s=$(date +%-S)
  now_total=$(( now_h * 3600 + now_m * 60 + now_s ))
  target_total=$(( target * 3600 ))
  if (( target_total <= now_total )); then
    target_total=$(( target_total + 86400 ))   # tomorrow
  fi
  echo $(( target_total - now_total ))
}

echo "[backup-loop] starting — daily at ${BACKUP_HOUR}:00 ${TZ:-UTC}, dir=$BACKUP_DIR, remote=${RCLONE_REMOTE:-<none>}"
run_backup   # baseline on boot

while true; do
  sleep_for=$(seconds_until_hour "$BACKUP_HOUR")
  echo "[backup-loop] sleeping ${sleep_for}s until next ${BACKUP_HOUR}:00"
  sleep "$sleep_for"
  run_backup
done
