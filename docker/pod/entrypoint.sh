#!/bin/bash
# Pod image PID 1 until supervisord takes over (spec §4): environment, safety rules, then a
# normal start, a restore or a fresh init, then exec supervisord. A refusal (lib.sh refuse) keeps
# the container alive for SSH; this script never exits into a restart loop.
set -uo pipefail
source /usr/src/app/docker/pod/lib.sh
LOG_TAG=entrypoint

MARKER="$POD_STATE_DIR/cluster-in-progress"
RESTORE_TIMEOUT=900
TEMP_PG_UP=0
FAILURE=''

on_term() {
  log "SIGTERM before supervisord started; stopping"
  [ "$TEMP_PG_UP" = 1 ] && temp_pg_stop immediate
  exit 0
}
trap on_term TERM INT

# --- Postgres, started briefly over the local socket only -------------------------------

psql_local() { as_postgres psql -X -q -v ON_ERROR_STOP=1 -At "$@"; }

# temp_pg_start wait|nowait on|blocked|off: the second argument is the archiving mode.
#   on       a normal start archives as usual. With archiving off, a checkpoint would delete WAL
#            files still waiting to be archived.
#   blocked  a restore: archiving on, but archive_command=false. Postgres queues every finished
#            file (the new timeline's history and segments) while nothing reaches the volume, so a
#            refused restore leaves the archive untouched. supervisord's Postgres archives the
#            queue. With archiving off, segments the new timeline finished here would never be
#            archived.
#   off      a fresh init: nothing written before the first base backup is ever needed.
# No log file: the temporary server's log goes to the container log (RESTORE ERROR lines too).
temp_pg_start() {
  local opts="-c listen_addresses=''"
  case "$2" in
    on) ;;
    blocked) opts+=" -c archive_mode=on -c archive_command=false" ;;
    off) opts+=" -c archive_mode=off" ;;
  esac
  if [ "$1" = wait ]; then
    as_postgres pg_ctl -D "$PGDATA" -o "$opts" -w -t 300 start || return 1
  else
    as_postgres pg_ctl -D "$PGDATA" -o "$opts" -W start || return 1
  fi
  TEMP_PG_UP=1
}

temp_pg_stop() {  # temp_pg_stop fast|immediate
  as_postgres pg_ctl -D "$PGDATA" -m "$1" -w -t 60 stop
  TEMP_PG_UP=0
}

# The environment (a Runpod Secret) is authoritative, so the password can be rotated (spec §4.2).
apply_password() {
  psql_local -v usr="$POSTGRES_USER" -v pw="$POSTGRES_PASSWORD" <<'SQL'
ALTER ROLE :"usr" PASSWORD :'pw';
SQL
}

# POSTGRES_USER and POSTGRES_DB can't change after the first boot: say so instead of letting
# the app crash-loop.
check_role_and_database() {
  if ! apply_password; then
    FAILURE="could not set the password of role \"$POSTGRES_USER\" (POSTGRES_USER must not change after the first boot)"
    return 1
  fi
  if [ "$(psql_local -v db="$POSTGRES_DB" <<< "SELECT count(*) FROM pg_database WHERE datname = :'db';")" != 1 ]; then
    FAILURE="the database \"$POSTGRES_DB\" does not exist (POSTGRES_DB must not change after the first boot)"
    return 1
  fi
}

# Image settings win on every boot, also over restored data (spec §4.2).
write_pg_conf() {
  install -d -o postgres -g postgres -m 700 "$PGDATA/conf.d"
  render_pg_conf "$POD_DIR/postgresql.pod.conf" > "$PGDATA/conf.d/gateway.conf" &&
    chown postgres:postgres "$PGDATA/conf.d/gateway.conf"
}

new_pgdata() {
  rm -rf "$PGDATA"
  install -d -o postgres -g postgres -m 700 "$PGDATA"
}

# --- the three boot paths (spec §4.2, §4.4, §4.5) ---------------------------------------

normal_start() {
  # Nothing can be running at container start; after a crash a stale PID file may name a live
  # process of the new PID namespace and stop Postgres from starting.
  rm -f "$PGDATA/postmaster.pid"
  write_pg_conf || { FAILURE='could not write the Postgres settings'; return 1; }
  temp_pg_start wait on || { FAILURE='Postgres did not start (see its log above)'; return 1; }
  check_role_and_database || { temp_pg_stop fast; return 1; }
  temp_pg_stop fast
}

fresh_init() {
  touch "$MARKER"
  new_pgdata
  as_postgres initdb -D "$PGDATA" --wal-segsize=1 --auth-local=peer --auth-host=scram-sha-256 -U postgres >/dev/null ||
    { FAILURE='initdb failed'; return 1; }
  # Keep initdb's pg_hba.conf: local peer, 127.0.0.1/::1 scram, and the replication lines
  # pg_basebackup needs.
  printf "\ninclude_dir = 'conf.d'\n" >> "$PGDATA/postgresql.conf"
  write_pg_conf || { FAILURE='could not write the Postgres settings'; return 1; }
  temp_pg_start wait off || { FAILURE='Postgres did not start (see its log above)'; return 1; }
  if ! psql_local -v usr="$POSTGRES_USER" -v pw="$POSTGRES_PASSWORD" -v db="$POSTGRES_DB" <<'SQL'
CREATE ROLE :"usr" LOGIN PASSWORD :'pw';
CREATE DATABASE :"db" OWNER :"usr";
SQL
  then
    temp_pg_stop immediate
    FAILURE='could not create the role and database'
    return 1
  fi
  temp_pg_stop fast
  rm -f "$MARKER"
  touch "$POD_STATE_DIR/needs-base-backup"
  log "fresh init complete"
}

# Poll until recovery has ended: pg_ctl's own readiness fires at consistency, before the end.
wait_for_promotion() {
  local deadline=$((SECONDS + RESTORE_TIMEOUT)) state
  # pg_ctl -W returns before the postmaster has written its PID file.
  for _ in $(seq 30); do
    [ -f "$PGDATA/postmaster.pid" ] && break
    sleep 1
  done
  while :; do
    as_postgres pg_ctl -D "$PGDATA" status >/dev/null || { FAILURE='Postgres stopped during recovery (see its log above)'; return 1; }
    state=$(psql_local -c 'SELECT pg_is_in_recovery()' 2>/dev/null)
    [ "$state" = f ] && return 0
    [ "$SECONDS" -lt "$deadline" ] || { FAILURE="recovery did not finish within $((RESTORE_TIMEOUT / 60)) minutes"; return 1; }
    sleep 1
  done
}

restore_cluster() {
  local started=$SECONDS backup tli
  touch "$MARKER"
  rm -f "$POD_STATE_DIR/restore-corrupt"
  backup=$(newest_complete_backup "$BACKUP_DIR/base")
  log "restoring from base backup $(basename "$backup")"
  new_pgdata
  extract_tar "$backup/base.tar.gz" "$PGDATA" && extract_tar "$backup/pg_wal.tar.gz" "$PGDATA/pg_wal" ||
    { FAILURE="could not extract base backup $(basename "$backup")"; return 1; }
  chown -R postgres:postgres "$PGDATA" && chmod 700 "$PGDATA"
  write_pg_conf || { FAILURE='could not write the Postgres settings'; return 1; }
  # No recovery target: replay to the end of the archive on the latest timeline, then promote.
  printf "restore_command = '%s %%f %%p'\n" "$POD_DIR/restore-wal.sh" > "$PGDATA/conf.d/zz-restore.conf"
  touch "$PGDATA/recovery.signal"
  chown postgres:postgres "$PGDATA/conf.d/zz-restore.conf" "$PGDATA/recovery.signal"

  temp_pg_start nowait blocked || { FAILURE='Postgres did not start (see its log above)'; return 1; }
  wait_for_promotion || { temp_pg_stop immediate; return 1; }
  if [ -e "$POD_STATE_DIR/restore-corrupt" ]; then
    temp_pg_stop immediate
    FAILURE='an archived WAL file is corrupt (see the RESTORE ERROR line above)'
    return 1
  fi
  check_role_and_database || { temp_pg_stop immediate; return 1; }
  temp_pg_stop fast
  rm -f "$PGDATA/conf.d/zz-restore.conf"

  tli=$(LC_ALL=C pg_controldata "$PGDATA" | sed -n "s/^Latest checkpoint's TimeLineID: *//p")
  restore_complete "$BACKUP_DIR/wal" "$PGDATA/pg_wal/$(printf '%08X' "$tli").history" ||
    { FAILURE='recovery stopped before the end of the archive (an archived WAL file is missing)'; return 1; }

  rm -f "$MARKER"
  touch "$POD_STATE_DIR/needs-base-backup"
  owner_fence && printf '%s %ss\n' "$(utc_stamp)" "$((SECONDS - started))" > "$BACKUP_DIR/status/last-restore"
  log "restore complete: timeline $tli in $((SECONDS - started)) s"
}

# --- boot -------------------------------------------------------------------------------

apply_defaults
missing=$(missing_required_env)
[ -z "$missing" ] || refuse "missing required environment variables: $missing" 'Refusals'
derive_hosts  # can't fail: RUNPOD_POD_ID is required
# Left over if the container restarted with its disk; backup-reset reads it.
rm -f "$SUPERVISORD_PIDFILE"
volume_ready || refuse "no network volume mounted at $VOLUME_MOUNT, or $BACKUP_DIR is not writable" 'Refusals'

mkdir -p "$BACKUP_DIR/base" "$BACKUP_DIR/wal" "$BACKUP_DIR/dumps" "$BACKUP_DIR/status"
# Needed on a real filesystem (the local drill); on Runpod's MooseFS volume any non-root user can write.
chown postgres:postgres "$BACKUP_DIR/wal" 2>/dev/null || true
install -d -o postgres -g postgres -m 755 "$POD_STATE_DIR"
install -d -o postgres -g postgres -m 2775 /var/run/postgresql

owner_check || refuse "the backup folder belongs to pod '$(volume_owner)', this pod is '$RUNPOD_POD_ID'" 'Refusals'
write_env_file "$GATEWAY_POD_ENV_FILE" "${POD_ENV_VARS[@]}" || refuse "could not write $GATEWAY_POD_ENV_FILE" 'Refusals'

decision=$(boot_decision)
log "boot decision: $decision"
case "$decision" in
  normal) normal_start || refuse "$FAILURE" 'Refusals' ;;
  restore) restore_cluster || refuse "restore failed: $FAILURE" 'Refusals' ;;
  fresh) fresh_init || refuse "fresh init failed: $FAILURE" 'Refusals' ;;
  refuse-no-base) refuse 'archived WAL exists on the volume but no complete base backup' 'Refusals' ;;
esac

trap - TERM INT
exec supervisord -n -c /usr/src/app/docker/pod/supervisord.conf
