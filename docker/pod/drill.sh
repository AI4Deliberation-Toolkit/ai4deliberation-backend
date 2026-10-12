#!/bin/bash
# Local restore drill for the pod image (spec §9.2). Needs Docker. Run from the repo root:
#   docker/pod/drill.sh            # build the image, run every scenario, clean up
#   docker/pod/drill.sh --keep     # leave the containers and volumes for inspection
#   docker/pod/drill.sh busy_crash # one scenario that sets up its own volume (busy_crash only;
#                                  # the others build on each other's state)
# Named Docker volumes stand in for the Runpod network volume at /workspace. Prints PASS/FAIL per
# check, the measured stop phases and restore times; exits non-zero if any check failed.
set -uo pipefail
cd "$(dirname "$0")/../.."

IMAGE=${DRILL_IMAGE:-gateway-pod:drill}
LABEL=gateway-pod-drill
KEYS=$(python3 -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')  # a Fernet key
PASSWORD="dr'il\"l\$pa(ss)!"                           # quote, double quote, dollar, parens, bang
FAILURES=0

# --- helpers ----------------------------------------------------------------------------

title() { printf '\n=== %s\n' "$*"; }
pass() { printf '  PASS %s\n' "$*"; }
fail() { printf '  FAIL %s\n' "$*"; FAILURES=$((FAILURES + 1)); }
check() {  # check DESCRIPTION COMMAND...
  local what=$1
  shift
  if "$@"; then pass "$what"; else fail "$what"; fi
}

cleanup() {
  docker rm -f $(docker ps -aq --filter "label=$LABEL") >/dev/null 2>&1
  docker volume rm $(docker volume ls -q --filter "label=$LABEL") >/dev/null 2>&1
  return 0
}

new_volume() { docker volume create --label "$LABEL" "drill-$1" >/dev/null; }

# start NAME VOLUME|- POD_ID [docker run args...]; later -e values override the defaults.
start() {
  local name=$1 volume=$2 pod=$3 mount=()
  shift 3
  [ "$volume" = - ] || mount=(-v "drill-$volume:/workspace")
  docker run -d --name "$name" --label "$LABEL" "${mount[@]}" \
    -e RUNPOD_POD_ID="$pod" -e SECRET_KEY=drill-secret -e GATEWAY_ENCRYPTION_KEYS="$KEYS" \
    -e POSTGRES_DB=gateway -e POSTGRES_USER=gateway -e POSTGRES_PASSWORD="$PASSWORD" \
    -e BACKUP_CHECK_INTERVAL=5 "$@" "$IMAGE" >/dev/null
}

replace() {  # replace OLD NEW VOLUME POD [args...]: the old container goes, a new one (empty disk) starts
  local old=$1
  shift
  docker rm -f "$old" >/dev/null
  start "$@"
}

log_count() { docker logs "$1" 2>&1 | grep -c -- "$2"; }

wait_log() {  # wait_log NAME PATTERN TIMEOUT [COUNT]
  local deadline=$((SECONDS + $3)) count=${4:-1}
  until [ "$(log_count "$1" "$2")" -ge "$count" ]; do
    if [ "$SECONDS" -ge "$deadline" ]; then
      echo "  timed out after $3 s waiting for '$2' in $1; last lines:"
      docker logs --tail 25 "$1" 2>&1 | sed 's/^/    | /'
      return 1
    fi
    sleep 1
  done
}

wait_ready() {  # wait_ready NAME: until /api/v1/health answers 200 (Postgres and the app are up)
  local deadline=$((SECONDS + 120))
  until http_ok "$1" /api/v1/health 2>/dev/null; do
    if [ "$SECONDS" -ge "$deadline" ]; then
      echo "  timed out after 120 s waiting for $1 to answer /api/v1/health; last lines:"
      docker logs --tail 25 "$1" 2>&1 | sed 's/^/    | /'
      return 1
    fi
    sleep 1
  done
}

wait_refused() { wait_log "$1" 'GATEWAY POD REFUSED' 120; }

refused_with() {  # grep on a variable: `docker logs | grep -q` fails under pipefail when grep exits early
  local logs
  logs=$(docker logs "$1" 2>&1)
  grep -q "GATEWAY POD REFUSED: .*$2" <<< "$logs" && return 0
  grep 'GATEWAY POD REFUSED' <<< "$logs" | sed 's/^/    | /'
  return 1
}

running() { [ "$(docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null)" = true ]; }

sql() { docker exec "$1" gosu postgres psql -XAtq -d gateway -c "$2"; }

shell() { docker exec "$1" gateway-manage shell -c "$2" >/dev/null; }

add_platform() { shell "$1" "from gateway.models import Platform; Platform.objects.create(name='$2', slug='$2')"; }

has_platform() { [ "$(sql "$1" "select count(*) from gateway_platform where slug = '$2'")" = 1 ]; }

timeline_is() { [ "$(sql "$1" 'select timeline_id from pg_control_checkpoint()')" = "$2" ]; }

http_status() {
  docker exec "$1" python -c "import sys, urllib.request
try: print(urllib.request.urlopen('http://127.0.0.1:8000' + sys.argv[1]).status)
except Exception as e: print(getattr(e, 'code', e))" "$2"
}

http_ok() { [ "$(http_status "$1" "$2")" = 200 ]; }

on_volume() {  # on_volume VOLUME COMMAND: a throwaway container with the volume mounted
  docker run --rm -v "drill-$1:/workspace" --entrypoint bash "$IMAGE" -c "$2"
}

complete_count() { on_volume "$1" 'ls -d /workspace/gateway-backup/base/*/COMPLETE 2>/dev/null | wc -l'; }

history_count() { on_volume "$1" 'ls /workspace/gateway-backup/wal/*.history.gz 2>/dev/null | wc -l'; }

wait_for_history() {  # wait_for_history VOLUME COUNT
  for _ in $(seq 30); do
    [ "$(history_count "$1")" -ge "$2" ] && return 0
    sleep 1
  done
  return 1
}

wait_archived() {  # wait_archived NAME SEGMENT: until SEGMENT is on the volume
  for _ in $(seq 30); do
    docker exec "$1" test -f "/workspace/gateway-backup/wal/$2.gz" && return 0
    sleep 1
  done
  echo "  segment $2 was not archived within 30 s"
  return 1
}

switch_and_wait() {  # close the current WAL segment and wait until it is archived
  wait_archived "$1" "$(sql "$1" 'select pg_walfile_name(pg_switch_wal())')"
}

first_boot() {  # first_boot NAME VOLUME POD: fresh init, app up, first base backup on the volume
  new_volume "$2"
  start "$1" "$2" "$3"
  wait_ready "$1" && wait_log "$1" 'base backup complete' 60
}

with_segments() {  # with_segments NAME: three more archived segments after the base backup
  local i
  for i in 1 2 3; do
    add_platform "$1" "segment-$i" && switch_and_wait "$1" || return 1
  done
}

print_stop_phases() {
  docker logs "$1" 2>&1 | grep -E 'received SIGTERM|stopped: (app|backup|postgres)' | sed 's/^/    | /'
}

stop_order_ok() {
  local order
  order=$(docker logs "$1" 2>&1 | grep -oE 'stopped: (app|backup|postgres)' | tr '\n' ' ')
  [ "$order" = 'stopped: app stopped: backup stopped: postgres ' ]
}

# --- scenarios --------------------------------------------------------------------------

scenario_first_boot() {
  title '1. First boot: fresh init, first base backup, data through gateway-manage'
  new_volume main
  start pod-1 main drill-1 -e GATEWAY_ENABLE_STUB=true
  check 'fresh init' wait_log pod-1 'boot decision: fresh' 60
  check 'app ready' wait_ready pod-1
  check 'first base backup within 60 s' wait_log pod-1 'base backup complete' 60
  shell pod-1 "from gateway.models import Platform, Tool; from gateway.keys import issue_key
p = Platform.objects.create(name='Drill', slug='drill'); issue_key(p, label='drill')
Tool.objects.create(tool_id='stub', name='Stub', base_url='http://127.0.0.1:8000/stub', depth='native', adapter='native', operations=['echo'])"
  check 'platform, key and tool stored' [ "$(sql pod-1 'select concat((select count(*) from gateway_platform), (select count(*) from gateway_apikey), (select count(*) from gateway_tool))')" = 111 ]
  check 'health answers 200' http_ok pod-1 /api/v1/health
  check 'admin CSS served without nginx' http_ok pod-1 /static/admin/css/base.css
  check 'supervisorctl sees three running programs' [ "$(docker exec pod-1 supervisorctl status | grep -c RUNNING)" = 3 ]
}

scenario_planned_stop() {
  title '2. Planned stop, new container: restore to timeline 2, nothing lost'
  add_platform pod-1 before-stop  # the last change, not waited for
  local started=$SECONDS
  docker stop -t 15 pod-1 >/dev/null
  local took=$((SECONDS - started))
  echo "  docker stop took ${took} s; supervisord's stop lines:"
  print_stop_phases pod-1
  check "stop within the 15 s window (${took} s)" [ "$took" -lt 15 ]
  check 'stop order app, backup, postgres' stop_order_ok pod-1
  replace pod-1 pod-2 main drill-1
  check 'restored' wait_log pod-2 'restore complete' 120
  docker logs pod-2 2>&1 | grep 'restore complete' | sed 's/^/    | /'
  check 'app ready' wait_ready pod-2
  check 'timeline 2' timeline_is pod-2 2
  check 'earlier data present' has_platform pod-2 drill
  check 'the last change before the stop is present' has_platform pod-2 before-stop
  check 'base backup after the restore' wait_log pod-2 'base backup complete' 60
  check 'timeline 2 history archived' wait_for_history main 1
}

scenario_crash() {
  title '3. Crash (SIGKILL), new container: restore to timeline 3 across the 1 -> 2 switch'
  add_platform pod-2 row-a
  check 'row A archived' switch_and_wait pod-2
  add_platform pod-2 row-b
  docker kill -s KILL pod-2 >/dev/null
  # Drop the timeline-2 base backups, so the restore replays from the timeline-1 backup and must
  # follow 00000002.history.
  on_volume main 'for d in /workspace/gateway-backup/base/*/; do grep -q "^00000002" "$d/COMPLETE" 2>/dev/null && rm -rf "$d"; done'
  replace pod-2 pod-3 main drill-1
  check 'restored' wait_log pod-3 'restore complete' 120
  docker logs pod-3 2>&1 | grep 'restore complete' | sed 's/^/    | /'
  check 'app ready' wait_ready pod-3
  check 'timeline 3' timeline_is pod-3 3
  check 'row A present' has_platform pod-3 row-a
  if has_platform pod-3 row-b; then echo '  info: row B present'; else echo '  info: row B absent (within the crash window)'; fi
  check 'base backup after the restore' wait_log pod-3 'base backup complete' 60
}

scenario_status() {
  title '6. backup-status prints every field'
  local out label
  out=$(docker exec pod-3 backup-status)
  printf '%s\n' "$out" | sed 's/^/    | /'
  for label in 'pod' 'volume owner' 'last archived WAL' 'last archive failure' 'newest base backup' \
               'base backups' 'newest dump' 'dumps' 'database size' 'last daily cycle' 'last restore' 'last purge' \
               'archived WAL files' 'flags'; do
    check "field: $label" grep -q "^$label: " <<< "$out"
  done
  check 'last restore recorded' grep -qE '^last restore: +[0-9]{8}T[0-9]{6}Z [0-9]+s$' <<< "$out"
}

# --- main -------------------------------------------------------------------------------

keep=0
if [ "${1:-}" = --keep ]; then keep=1; shift; fi
cleanup
[ "$keep" = 1 ] || trap cleanup EXIT
title "Building $IMAGE"
docker build -q -f docker/pod/Dockerfile -t "$IMAGE" . >/dev/null || { echo 'build failed'; exit 1; }

if [ $# -gt 0 ]; then
  for scenario in "$@"; do "scenario_$scenario"; done
else
  scenario_first_boot
  scenario_planned_stop
  scenario_crash
  scenario_status
fi

title "Done: $FAILURES failed check(s)"
[ "$FAILURES" = 0 ]
