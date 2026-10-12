#!/bin/bash
# Supervised backup program (spec §5.3): base backups, SQL dumps, retention, call-log purge.
# Checks every BACKUP_CHECK_INTERVAL seconds (default 300; BACKUP_FORCE_CYCLE=1 makes every check
# run the daily cycle, for drills). A failed step logs "BACKUP ERROR: <step>" and the next check
# retries; there are no alerts (spec §8). Runs as root; Postgres tools run as postgres.
set -uo pipefail
source "$(dirname "$(readlink -f "$0")")/lib.sh"
LOG_TAG=backup

WORK_DIR="$POD_STATE_DIR/work"
SLEEP_PID=''
trap '[ -n "$SLEEP_PID" ] && kill "$SLEEP_PID" 2>/dev/null; exit 0' TERM INT

backup_error() { log "BACKUP ERROR: $1" >&2; }

write_status() { owner_fence && printf '%s\n' "$2" > "$BACKUP_DIR/status/$1"; }

new_work_dir() {
  rm -rf "$WORK_DIR"
  install -d -o postgres -g postgres -m 700 "$WORK_DIR"
}

take_base_backup() {
  local stamp start_wal dest out="$WORK_DIR/base"
  owner_fence || { backup_error 'base backup (owner fence)'; return 1; }
  stamp=$(utc_stamp)
  new_work_dir
  as_postgres pg_basebackup -U postgres -Ft -z -X stream -c fast -D "$out" ||
    { backup_error 'base backup (pg_basebackup)'; return 1; }
  start_wal=$(tar -xzOf "$out/base.tar.gz" backup_label | start_wal_from_label)
  [ -n "$start_wal" ] || { backup_error 'base backup (no start WAL in backup_label)'; return 1; }
  dest="$BACKUP_DIR/base/$stamp"
  mkdir -p "$dest" &&
    cp "$out/base.tar.gz" "$out/pg_wal.tar.gz" "$out/backup_manifest" "$dest/" &&
    gzip -t "$dest/base.tar.gz" && gzip -t "$dest/pg_wal.tar.gz" &&
    sync -d "$dest/base.tar.gz" "$dest/pg_wal.tar.gz" "$dest/backup_manifest" ||
    { backup_error 'base backup (copy to the volume)'; return 1; }
  # COMPLETE is written last: a backup without it is ignored by the restore and later deleted.
  owner_fence || { backup_error 'base backup (owner fence)'; return 1; }
  printf '%s\n' "$start_wal" > "$dest/COMPLETE.tmp" && mv "$dest/COMPLETE.tmp" "$dest/COMPLETE" ||
    { backup_error 'base backup (COMPLETE)'; return 1; }
  rm -rf "$WORK_DIR"
  rm -f "$POD_STATE_DIR/needs-base-backup"
  write_status last-base-backup "$stamp"
  log "base backup complete: $stamp (start WAL $start_wal)"
}

take_dump() {
  local stamp dest
  owner_fence || { backup_error 'dump (owner fence)'; return 1; }
  stamp=$(utc_stamp)
  new_work_dir
  as_postgres pg_dump -Fc -d "$POSTGRES_DB" -f "$WORK_DIR/gateway.dump" || { backup_error 'dump (pg_dump)'; return 1; }
  dest="$BACKUP_DIR/dumps/gateway-$stamp.dump"
  cp "$WORK_DIR/gateway.dump" "$dest.tmp" && sync -d "$dest.tmp" && mv "$dest.tmp" "$dest" ||
    { backup_error 'dump (copy to the volume)'; return 1; }
  rm -rf "$WORK_DIR"
  write_status last-dump "$stamp"
  log "dump complete: $stamp"
}

apply_retention() {
  local dir file cutoff kept
  owner_fence || { backup_error 'retention (owner fence)'; return 1; }
  while read -r dir; do
    [ -n "$dir" ] && rm -rf "$dir"
  done < <(backups_to_delete "$BACKUP_DIR/base" "$KEEP_BASE_BACKUPS" "$KEEP_BASE_BACKUP_SECONDS" "$(date -u +%s)")
  mapfile -t kept < <(complete_backups "$BACKUP_DIR/base")
  if [ ${#kept[@]} -gt 0 ]; then
    # Lowest start segment among all kept backups, ignoring the timeline (spec §5.3).
    cutoff=$(wal_cutoff "${kept[@]}")
    pg_archivecleanup -b -x ".$ARCHIVE_FORMAT" "$BACKUP_DIR/wal" "$cutoff" || backup_error 'retention (pg_archivecleanup)'
  fi
  find "$BACKUP_DIR/wal" "$BACKUP_DIR/dumps" -maxdepth 1 -name '*.tmp' -mmin +10 -delete
  while read -r file; do
    [ -n "$file" ] && rm -f "$file"
  done < <(dumps_to_delete "$BACKUP_DIR/dumps" "$KEEP_DUMPS")
}

purge_call_logs() {
  "$POD_DIR/gateway-manage" purge_call_logs || { backup_error 'call-log purge'; return 1; }
  write_status last-purge "$(utc_stamp)"
}

# A failed step is logged and retried with the next cycle; a failed base backup is retried at
# the next check (base_backup_due).
daily_cycle() {
  take_base_backup
  take_dump
  apply_retention
  purge_call_logs
  write_status last-cycle "$(utc_stamp)"
  log 'daily cycle complete'
}

run_check() {
  case "$(base_backup_due "$BACKUP_DIR/base" "$POD_STATE_DIR/needs-base-backup" "$BACKUP_DIR/status/last-cycle" \
            "$(date -u +%s)" "${BACKUP_FORCE_CYCLE:-0}")" in
    base) take_base_backup ;;
    daily) daily_cycle ;;
  esac
}

# The first check may be due at once (after a fresh init or restore): wait for Postgres so it
# doesn't fail and wait a whole interval.
for _ in $(seq 120); do
  as_postgres pg_isready -q && break
  sleep 1
done

while :; do
  run_check
  sleep "${BACKUP_CHECK_INTERVAL:-300}" &
  SLEEP_PID=$!
  wait "$SLEEP_PID"
done
