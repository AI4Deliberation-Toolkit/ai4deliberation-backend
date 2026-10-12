# Shared shell functions for the pod image (spec §3.1). Sourced by the pod scripts and by
# tests/pod/; sourcing has no side effects beyond setting the path variables below.
# Every path can be overridden from the environment, which is how the tests point the
# functions at temporary directories.

: "${VOLUME_MOUNT:=/workspace}"
: "${BACKUP_DIR:=$VOLUME_MOUNT/gateway-backup}"
: "${PGDATA:=/var/lib/postgresql/gateway}"
: "${POD_STATE_DIR:=/var/lib/gateway-pod}"
: "${GATEWAY_POD_ENV_FILE:=/etc/gateway-pod.env}"
: "${SUPERVISORD_PIDFILE:=/run/supervisord.pid}"
POD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$POD_DIR/../.." && pwd)"

WAL_SEGMENT_BYTES=$((1024 * 1024))  # initdb --wal-segsize=1 (spec §4.5)
DAY_SECONDS=86400
KEEP_BASE_BACKUPS=3
# Base backups younger than this are kept too, so frequent restores (each takes a base backup)
# don't shrink the recovery window below ~3 days. BACKUP_KEEP_SECONDS overrides it (drills only).
KEEP_BASE_BACKUP_SECONDS=${BACKUP_KEEP_SECONDS:-$((3 * DAY_SECONDS))}
KEEP_DUMPS=7
# Formats the restore path can read, by file extension (spec §8: encryption can be added later).
ARCHIVE_FORMATS='gz'
ARCHIVE_FORMAT='gz'  # the format new files are written in

# Variables written to GATEWAY_POD_ENV_FILE for SSH sessions (spec §4.1 step 4, §7.4).
POD_ENV_VARS=(
  DJANGO_SETTINGS_MODULE SECRET_KEY GATEWAY_ENCRYPTION_KEYS
  POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD POSTGRES_HOST POSTGRES_PORT
  ALLOWED_HOSTS CSRF_TRUSTED_ORIGINS CORS_ALLOWED_ORIGINS DEBUG
  GATEWAY_ENABLE_STUB GATEWAY_STUB_KEY CALL_LOG_RETENTION_DAYS GUNICORN_WORKERS
  RUNPOD_POD_ID BACKUP_DIR PGDATA
)
REQUIRED_ENV=(SECRET_KEY GATEWAY_ENCRYPTION_KEYS POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD RUNPOD_POD_ID)

# --- logging and refusals ---------------------------------------------------------------

log() { printf '%s [%s] %s\n' "$(date -u +%FT%TZ)" "${LOG_TAG:-pod}" "$*"; }

utc_stamp() { date -u +%Y%m%dT%H%M%SZ; }

# "20261012T200524Z" -> seconds since the epoch.
stamp_to_epoch() {
  local s=$1
  date -u -d "${s:0:4}-${s:4:2}-${s:6:2} ${s:9:2}:${s:11:2}:${s:13:2}" +%s
}

# Log one GATEWAY POD REFUSED block and stay alive without starting anything, so the pod stays
# reachable over SSH (spec §4.3). Never returns; SIGTERM ends it cleanly (Runpod stop, or
# `kill 1` over SSH to restart the container).
refuse() {
  local reason=$1 section=$2
  printf '%s\n' \
    '========================================================================' \
    "GATEWAY POD REFUSED: $reason" \
    "Runbook: docker/pod/README.md, section \"$section\"" \
    'Nothing was started. The pod stays up so you can connect over SSH.' \
    '========================================================================'
  _REFUSE_SLEEP=
  trap 'kill "$_REFUSE_SLEEP" 2>/dev/null; exit 0' TERM INT
  while :; do
    sleep 3600 &
    _REFUSE_SLEEP=$!
    wait "$_REFUSE_SLEEP"
  done
}

# --- environment (spec §4.1) ------------------------------------------------------------

apply_defaults() {
  : "${DJANGO_SETTINGS_MODULE:=ai4deliberation_backend.settings.staging}"
  : "${POSTGRES_HOST:=127.0.0.1}"
  : "${POSTGRES_PORT:=5432}"
  : "${GUNICORN_WORKERS:=2}"
  export DJANGO_SETTINGS_MODULE POSTGRES_HOST POSTGRES_PORT GUNICORN_WORKERS BACKUP_DIR PGDATA
}

# Print the names of required variables that are unset or empty, space-separated.
missing_required_env() {
  local name missing=()
  for name in "${REQUIRED_ENV[@]}"; do
    [ -n "${!name:-}" ] || missing+=("$name")
  done
  printf '%s' "${missing[*]}"
}

# Fill ALLOWED_HOSTS / CSRF_TRUSTED_ORIGINS from the pod ID when unset or empty; values the
# operator set win. Fails only when a value is needed and RUNPOD_POD_ID is missing.
derive_hosts() {
  local proxy_host=''
  if [ -z "${ALLOWED_HOSTS:-}" ] || [ -z "${CSRF_TRUSTED_ORIGINS:-}" ]; then
    [ -n "${RUNPOD_POD_ID:-}" ] || return 1
    proxy_host="${RUNPOD_POD_ID}-8000.proxy.runpod.net"
  fi
  [ -n "${ALLOWED_HOSTS:-}" ] || ALLOWED_HOSTS="$proxy_host,127.0.0.1,localhost"
  [ -n "${CSRF_TRUSTED_ORIGINS:-}" ] || CSRF_TRUSTED_ORIGINS="https://$proxy_host"
  export ALLOWED_HOSTS CSRF_TRUSTED_ORIGINS
}

# write_env_file PATH NAME... : `export NAME=<value quoted with %q>` per set variable, mode 600,
# so values holding $ ( ) ! ' " survive being sourced (spec §4.1 step 4).
write_env_file() {
  local path=$1 name
  shift
  (umask 077 && : > "$path.tmp") || return 1
  for name in "$@"; do
    [ -n "${!name+set}" ] || continue
    printf 'export %s=%q\n' "$name" "${!name}" >> "$path.tmp" || return 1
  done
  chmod 600 "$path.tmp" && mv "$path.tmp" "$path"
}

# Print postgresql.pod.conf with ${POSTGRES_PORT} filled in (spec §5.1).
render_pg_conf() {
  local template
  template=$(<"$1") || return 1
  printf '%s\n' "${template//'${POSTGRES_PORT}'/$POSTGRES_PORT}"
}

# Sets POSTGRES_ENV to the command prefix that runs a program with only the variables Postgres
# and its archive/restore commands need, so the app's secrets aren't in its environment (spec §3.3).
# PGPORT points the client tools (psql, pg_basebackup, pg_dump, pg_isready) at the server's port.
postgres_env_cmd() {
  POSTGRES_ENV=(env -i "PATH=$PATH" "PGDATA=$PGDATA" "LANG=${LANG:-C.UTF-8}" "PGPORT=${POSTGRES_PORT:-5432}"
                "RUNPOD_POD_ID=${RUNPOD_POD_ID:-}" "BACKUP_DIR=$BACKUP_DIR")
}

as_postgres() {
  postgres_env_cmd
  "${POSTGRES_ENV[@]}" gosu postgres "$@"
}

# The network volume must be mounted and the backup folder writable (spec §4.3 rule 1).
volume_ready() {
  mountpoint -q "$VOLUME_MOUNT" && mkdir -p "$BACKUP_DIR" 2>/dev/null && [ -w "$BACKUP_DIR" ]
}

supervisord_running() {
  [ -f "$SUPERVISORD_PIDFILE" ] && kill -0 "$(cat "$SUPERVISORD_PIDFILE")" 2>/dev/null
}
