#!/bin/bash
# restore_command during a restore (spec §4.4): restore-wal.sh %f %p, run by Postgres as postgres.
# A missing file is the normal end of the archive: exit 1 quietly. A file that is present but
# won't decompress is corrupt: flag it, so the entrypoint refuses instead of accepting a
# promotion that stopped early.
set -uo pipefail
source "$(dirname "$(readlink -f "$0")")/lib.sh"
LOG_TAG=restore-wal

name=$1
dest=$2

src=$(archived_file "$BACKUP_DIR/wal" "$name") || exit 1

if ! decompress "$src" > "$dest.tmp"; then
  log "RESTORE ERROR corrupt $name" >&2
  touch "$POD_STATE_DIR/restore-corrupt"
  rm -f "$dest.tmp"
  exit 1
fi
mv "$dest.tmp" "$dest"
