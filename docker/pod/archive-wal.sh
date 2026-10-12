#!/bin/bash
# archive_command (spec §5.2): archive-wal.sh %p %f, run by Postgres as postgres from PGDATA.
# Copies one WAL segment, timeline history or backup history file to the volume, compressed.
# Non-zero means Postgres keeps the file and retries later (it logs each failure); it archives
# the oldest ready file first, so a failure never leaves a gap.
set -uo pipefail
source "$(dirname "$(readlink -f "$0")")/lib.sh"
LOG_TAG=archive-wal

src=$1
name=$2
dest="$BACKUP_DIR/wal/$name.$ARCHIVE_FORMAT"

owner_fence || exit 1

if [ -e "$dest" ]; then
  # Postgres may retry a file it archived just before a crash: the same content is a success.
  decompress "$dest" | cmp -s - "$src" && exit 0
  if decompress "$dest" > /dev/null 2>&1; then
    log "ARCHIVE ERROR $name: a different file with this name is already archived" >&2
    exit 1
  fi
  # The archived copy is damaged (it won't decompress): replace it with the good one.
  log "replacing the damaged archived copy of $name"
fi

if ! { gzip -c -- "$src" > "$dest.tmp" && sync -d "$dest.tmp" && mv "$dest.tmp" "$dest"; }; then
  log "ARCHIVE ERROR $name: copy to the volume failed" >&2
  rm -f "$dest.tmp"
  exit 1
fi
