# Gateway pod on Runpod: runbook

The gateway runs on its own CPU pod on Runpod, with PostgreSQL inside the pod. The live database
sits on the container disk, which Runpod erases on every stop or Edit Pod. Continuous WAL
archiving, daily base backups and daily dumps go to a network volume at `/workspace`, and every
boot on an empty container disk restores from that volume. A planned stop or Edit Pod loses
nothing; a crash loses at most about 60 seconds of changes.

Design: `docs/superpowers/specs/2026-10-12-gateway-runpod-pod-design.md` (local only). Staging is
separate and unchanged: it still deploys from GitLab with `docker-compose-staging.yml`.

## Contents

1. [Prerequisites](#1-prerequisites)
2. [First deploy](#2-first-deploy)
3. [Update the image](#3-update-the-image)
4. [Replace the pod](#4-replace-the-pod)
5. [Refusals](#5-refusals)
6. [Manual restore, point-in-time recovery, dumps](#6-manual-restore-point-in-time-recovery-dumps)
7. [Drills](#7-drills)
8. [Reference](#8-reference)

## 1. Prerequisites

- Access to the project's Runpod account, with your SSH public key added under Settings → SSH Public Keys.
- The image tag to deploy: `ghcr.io/ai4deliberation-toolkit/ai4deliberation-backend-pod:<short sha>`,
  built by the `pod-image` GitHub Actions workflow on every push to `main`. Use the short-SHA tag,
  never `:latest`, so the pod changes only when you edit it. The package is public, so Runpod
  pulls it without registry credentials.
- A Fernet key for `GATEWAY_ENCRYPTION_KEYS`:
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
  **Keep a copy outside Runpod** (the team password manager). Without it, the tool keys in a
  restored database can't be decrypted.

## 2. First deploy

1. **Secrets.** In Runpod → Secrets, create `gateway_secret_key` (a long random string),
   `gateway_encryption_keys` (the Fernet key) and `gateway_postgres_password` (a long random string).
   With the stub, also `gateway_stub_key` (a long random string).
2. **Network volume.** Storage → New Network Volume: an EU datacenter that offers CPU pods, Secure
   Cloud, 10 GB. The pod has to run in this datacenter for good.
3. **Pod.** Deploy a CPU pod in that datacenter, with the network volume attached (a volume can
   only be attached when the pod is created):
   - Container image: the short-SHA tag from §1. Container start command: empty.
   - Container disk: 10 GB. Volume mount path: `/workspace`.
   - Expose HTTP port `8000`.
   - Environment variables:

     | Variable | Value |
     |---|---|
     | `SECRET_KEY` | `{{ RUNPOD_SECRET_gateway_secret_key }}` |
     | `GATEWAY_ENCRYPTION_KEYS` | `{{ RUNPOD_SECRET_gateway_encryption_keys }}` |
     | `POSTGRES_PASSWORD` | `{{ RUNPOD_SECRET_gateway_postgres_password }}` |
     | `POSTGRES_DB` | `gateway` |
     | `POSTGRES_USER` | `gateway` |

     With the stub, add `GATEWAY_ENABLE_STUB` = `true` and `GATEWAY_STUB_KEY` =
     `{{ RUNPOD_SECRET_gateway_stub_key }}`.

     Leave `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` unset: they're derived from the pod ID. The
     secret references resolve (checked on the first deploy, 2026-10-18). If they ever stop
     resolving (check over SSH: `tr '\0' '\n' < /proc/1/environ | grep -c RUNPOD_SECRET` prints `0`
     when they resolve), use the plain values instead.
4. **Logs.** In the pod's logs, expect `boot decision: fresh`, `fresh init complete`, supervisord
   starting `postgres`, `backup` and `app`, then `base backup complete` within about a minute.
5. **Admin user.** Connect with the SSH command the pod's Connect tab shows
   (`ssh <podid>-<hash>@ssh.runpod.io -i ~/.ssh/<key>`), then run `gateway-manage createsuperuser`.
6. **Check.** `https://<podid>-8000.proxy.runpod.net/api/v1/health` answers 200, and
   `https://<podid>-8000.proxy.runpod.net/admin/` shows the styled login page. Run `backup-status`
   over SSH.
7. **Register.** In the admin: the WordPress platform and its API key, the topic toolkit, and the
   stub if you want it (`GATEWAY_ENABLE_STUB=true`, with `GATEWAY_STUB_KEY`).
8. **Smoke test** (`URL=https://<podid>-8000.proxy.runpod.net`, `KEY=<the platform key>`):

   ```bash
   curl -s "$URL/api/v1/tools" -H "X-Gateway-Key: $KEY"           # the registered tools
   curl -s "$URL/api/v1/tools/stub/echo" -H "X-Gateway-Key: $KEY" \
        -H 'Content-Type: application/json' -d '{"input": {"text": "hello"}}'   # if the stub is on
   curl -s -o /dev/null -w '%{http_code}\n' "$URL/api/v1/tools" -H "X-Gateway-Key: wrong"   # 401
   ```

   Then make one real call per registered tool, and check that each call shows up under Call logs
   in the admin.

## 3. Update the image

1. Wait for the `pod-image` workflow on the new `main` commit to finish, and note its short-SHA tag.
2. Pod → Edit Pod → Container image → the new tag → Save. Runpod stops the container (a planned
   stop: everything gets archived) and starts the new image on an empty container disk.
3. In the logs: `boot decision: restore`, `restore complete: timeline N in S s`, then the app.
   Expect 30–60 s without service.
4. Over SSH: `backup-status`. A new base backup appears within a minute.

## 4. Replace the pod

Use this when the host has died, or to move to a new pod in the volume's datacenter.

1. **Stop or terminate the old pod first.** Only one pod may write to the backup folder. An old
   pod that keeps running after the takeover can't write to it, but its changes from then on are lost.
2. Note the old pod's ID (the volume's `OWNER` file holds it; `backup-status` shows it as `volume owner`).
3. Create a new pod as in §2 step 3, on the same network volume, with one extra variable:
   `BACKUP_TAKEOVER=<old pod ID>`.
4. In the logs: `backup folder taken over from pod <old ID>`, then a restore. You can leave
   `BACKUP_TAKEOVER` set; it no longer matches once the takeover is done.
5. The proxy URL changes with the pod ID. Update the platforms that call the gateway.

## 5. Refusals

When it's unsafe to start, the pod logs one block and starts nothing:

```
========================================================================
GATEWAY POD REFUSED: <reason>
Runbook: docker/pod/README.md, section "Refusals"
...
```

The container stays up so you can connect over SSH. To try again after fixing the cause, restart
the container: over SSH, `kill 1` (Runpod starts the container again and keeps the container
disk). Or use Stop then Start in the console, which also erases the container disk; both are fine here.

| Reason starts with | Meaning | What to do |
|---|---|---|
| `missing required environment variables` | A required variable is unset or empty. | Edit Pod, add it (see §8). |
| `no network volume mounted at /workspace` | The pod has no network volume, or a different mount path. | A volume can only be attached at pod creation. Create a new pod with the volume at `/workspace`. |
| `the backup folder belongs to pod '<id>'` | Another pod owns the backups. | If that pod is gone or stopped for good, follow §4 (`BACKUP_TAKEOVER=<id>`). Otherwise you attached the wrong volume. |
| `restore failed: could not extract base backup` | The newest base backup is damaged. | §6.3. |
| `restore failed: an archived WAL file is corrupt` | A WAL file in `wal/` won't decompress. The log names it (`RESTORE ERROR corrupt <file>`). | §6.3. |
| `restore failed: recovery stopped before the end of the archive` | A WAL file is missing from the middle of the archive, so later changes can't be replayed. | §6.3. |
| `restore failed: recovery did not finish within 15 minutes` / `Postgres stopped during recovery` | See the Postgres lines just above the block. | Fix the cause if the log names one (e.g. disk full: a bigger container disk). Otherwise §6.3. |
| `Postgres did not start` | The Postgres lines above the block say why. | Usually a full container disk: Edit Pod, larger container disk. |
| `could not write` | `could not write /etc/gateway-pod.env`, or `could not write the Postgres settings`. | Container disk full or read-only: Edit Pod, larger container disk. |
| `could not set the password of role` | `POSTGRES_USER` differs from the first boot. | Put back the original value. It can never change. |
| `the database "<name>" does not exist` | `POSTGRES_DB` differs from the first boot. | Put back the original value. It can never change. |
| `archived WAL exists on the volume but no complete base backup` | A stop before the first base backup finished (the first minutes after the first deploy). | Nothing is worth keeping: `backup-reset --yes`, then `kill 1` for a fresh start. |
| `fresh init failed` | `initdb failed`, or `could not create the role and database`. | See the lines above. Usually disk space. |

`backup-reset --yes` moves `/workspace/gateway-backup` aside to
`/workspace/gateway-backup.<UTC time>.aside`. The next boot then starts with an empty database.
It refuses while the gateway runs. Delete the aside folder once you're sure you don't need it.

## 6. Manual restore, point-in-time recovery, dumps

All commands run over SSH, as root.

### 6.1 Point-in-time recovery from a chosen base backup

Use this to undo a mistake (for example, rows deleted at 14:05): restore the database as it was
at a given time.

Pick the newest base backup that **finished** before the target time. A backup folder is named
by its start time; its `COMPLETE` file was written when it finished:

```bash
source /usr/src/app/docker/pod/lib.sh            # paths: PGDATA, BACKUP_DIR, POD_STATE_DIR
ls -l --time-style=+%FT%TZ "$BACKUP_DIR"/base/*/COMPLETE   # finish times (UTC)
B="$BACKUP_DIR/base/<chosen timestamp>"
supervisorctl stop app backup postgres
mv "$PGDATA" "$PGDATA.before-pitr"                # keep the current data until you're sure
install -d -o postgres -g postgres -m 700 "$PGDATA"
tar -xzf "$B/base.tar.gz" -C "$PGDATA"
tar -xzf "$B/pg_wal.tar.gz" -C "$PGDATA/pg_wal"
cat > "$PGDATA/conf.d/zz-restore.conf" <<'EOF'
restore_command = '/usr/src/app/docker/pod/restore-wal.sh %f %p'
recovery_target_time = '2026-10-20 14:04:00+00'
recovery_target_action = 'promote'
EOF
touch "$PGDATA/recovery.signal"
chown -R postgres:postgres "$PGDATA"
rm -f "$POD_STATE_DIR/restore-corrupt"
supervisorctl start postgres
```

Wait for `recovery stopping before ...` and `database system is ready to accept connections` in
the logs. If Postgres instead stops with `recovery ended before configured recovery target was
reached`, the backup finished after the target, or the target lies past the end of the archive.
Then: `supervisorctl stop postgres`, and either start over from the `mv` step with an older backup
or correct `recovery_target_time`, then `supervisorctl start postgres`. Once the logs show the
recovery stopping at the target:

```bash
test -e "$POD_STATE_DIR/restore-corrupt" && echo "CORRUPT FILE: check the logs before going on"
rm "$PGDATA/conf.d/zz-restore.conf"
touch "$POD_STATE_DIR/needs-base-backup"         # the backup loop takes a base backup at once
supervisorctl start backup app
backup-status                                     # a new base backup within a minute
```

When the data is right, delete `$PGDATA.before-pitr`. The recovery starts a new timeline; later
automatic restores follow it.

### 6.2 Restoring a dump

Dumps (`$BACKUP_DIR/dumps/gateway-<UTC time>.dump`, `pg_dump -Fc`) are the portable copy.

- To inspect one next to the live database:
  `gosu postgres createdb -O gateway inspect && gosu postgres pg_restore --no-owner --role=gateway -d inspect "$BACKUP_DIR/dumps/<file>"`.
  Drop it afterwards with `gosu postgres dropdb inspect`.
- To move to a managed Postgres (spec §12):
  `pg_restore --no-owner -d "postgresql://<user>:<password>@<host>:<port>/<db>" <file>`.
  Then run the gateway with `POSTGRES_HOST` and the other `POSTGRES_*` variables pointing there.

### 6.3 A damaged archive

The pod refused because a base backup or WAL file is damaged. Nothing has been changed.

- **Damaged newest base backup.** Move it aside: `mv "$BACKUP_DIR/base/<ts>" "$BACKUP_DIR/damaged-<ts>"`,
  then `kill 1`. The restore uses the next newest base backup and replays the archive from there.
- **Corrupt or missing WAL file.** Changes after that file can't be replayed. The refused restore
  has already recovered everything up to it and stopped. Choose one:
  - **Keep everything up to the damaged file** (the local drill runs exactly these steps). In
    the refused container, without restarting it first:

    ```bash
    source /usr/src/app/docker/pod/lib.sh
    # Only if the log named a corrupt file (RESTORE ERROR corrupt <file>): keep it for the record.
    mv "$BACKUP_DIR/wal/<file>.gz" "$BACKUP_DIR/damaged-<file>.gz"
    rm -f "$PGDATA/conf.d/zz-restore.conf" "$POD_STATE_DIR/cluster-in-progress" "$POD_STATE_DIR/restore-corrupt"
    touch "$POD_STATE_DIR/needs-base-backup"
    kill 1     # restarts the container with its disk: a normal start on the recovered data
    ```

    Don't use Stop → Start here: it erases the container disk, and with it the recovered data.
  - **Use the newest dump instead** (at most a day old; changes after it are lost). First keep a
    copy of the dump outside the backup folder, which `backup-reset` moves aside:

    ```bash
    source /usr/src/app/docker/pod/lib.sh
    ls -1 "$BACKUP_DIR"/dumps/                      # pick the newest gateway-<UTC time>.dump
    cp "$BACKUP_DIR/dumps/<file>" /root/restore.dump
    backup-reset --yes
    kill 1     # fresh start with an empty gateway database
    ```

    Once the pod is up again (the logs show `fresh init complete` and the app), connect over SSH
    again and load the dump with the app stopped:

    ```bash
    source /usr/src/app/docker/pod/lib.sh
    supervisorctl stop app
    gosu postgres pg_restore --no-owner --role=gateway --clean --if-exists -d gateway < /root/restore.dump
    touch "$POD_STATE_DIR/needs-base-backup"         # a base backup of the restored data at once
    supervisorctl start app
    backup-status
    ```

    `/root` is on the container disk: it survives `kill 1`, not Stop → Start. The `.aside` folder
    still holds the dump too.

## 7. Drills

Run these after the first deploy and after big changes to the image.

1. **Edit Pod:** Runpod won't save an unchanged pod, so make a change with no effect: add
   `GUNICORN_WORKERS=2` (the default), or remove it if it's already there. The data is still there afterwards.
2. **Stop → Start:** the data is still there afterwards.
3. **Crash:** write a row (e.g. a test platform in the admin), wait more than 70 s, write a second
   row. Over SSH, `pkill -STOP -u postgres` freezes Postgres and its archiver, so the graceful
   shutdown can't finish. Then Stop Pod: Runpod's kill fires about 15 s later. After Start, the
   first row is there; the second may be missing.
4. `backup-status` looks sane, and `last restore` shows the restore time. After every restore,
   `last archive failure` names the new timeline's `.history` file with one failure. That's
   expected: archiving is blocked on purpose while the restore runs, and the file is archived
   seconds later by the regular Postgres. It's only a problem if `last archived WAL` is older
   than the failure.

Measured on Runpod (pod `r4k4bs0w6yyryd`, image `9642d03`, 2026-10-18/19): every restore took
4 s (Edit Pod twice, Stop → Start, crash). In the crash drill, the first row survived and the second
was lost. Archiving to the network volume works: a manual `pg_switch_wal()` was archived at once.
`kill 1` restarts the container with its disk (§5). The SSH session has the pod's environment
(`RUNPOD_POD_ID` is set).

Locally, `docker/pod/drill.sh` runs the full drill against a Docker volume (spec §9.2).

## 8. Reference

### Environment variables

| Variable | Value | Notes |
|---|---|---|
| `SECRET_KEY` | secret | Runpod Secret |
| `GATEWAY_ENCRYPTION_KEYS` | secret | Runpod Secret; comma-separated Fernet keys, the first one encrypts; keep a copy outside Runpod |
| `POSTGRES_PASSWORD` | secret | Runpod Secret; applied on every boot, so you can rotate it: change the secret, then restart |
| `POSTGRES_DB`, `POSTGRES_USER` | e.g. `gateway` | never change after the first boot |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | leave unset | derived from the pod ID; set both only for a custom hostname (`ALLOWED_HOSTS` must then still list `127.0.0.1,localhost`) |
| `USE_X_FORWARDED_HOST` | leave unset | `true` in the pod: Runpod's proxy sends the pod's internal address as `Host` and the public host as `X-Forwarded-Host`, which is still checked against `ALLOWED_HOSTS` |
| `GATEWAY_ENABLE_STUB`, `GATEWAY_STUB_KEY` | optional | stub off by default |
| `GUNICORN_WORKERS` | optional | default 2 |
| `BACKUP_TAKEOVER` | only when replacing the pod | §4 |
| `DEBUG`, `CORS_ALLOWED_ORIGINS`, `CALL_LOG_RETENTION_DAYS` | optional | as on staging; call logs older than `CALL_LOG_RETENTION_DAYS` (180) are purged daily |

### Commands (over SSH)

| Command | What it does |
|---|---|
| `backup-status` | Archiving, base backups, dumps, database size, last daily cycle, restore and purge, flags |
| `gateway-manage <command>` | `manage.py` with the pod's environment, e.g. `createsuperuser`, `check_tools` |
| `backup-reset --yes` | Moves the backup folder aside for a fresh start (refused pods only) |
| `supervisorctl status` / `stop` / `start` | The `postgres`, `backup` and `app` programs |

### What is where

| Path | Content |
|---|---|
| `/var/lib/postgresql/gateway` | Live database (container disk) |
| `/workspace/gateway-backup/base/<UTC time>/` | Base backups: `base.tar.gz`, `pg_wal.tar.gz`, `backup_manifest`, `COMPLETE` (written last) |
| `/workspace/gateway-backup/wal/` | Archived WAL, `<name>.gz` |
| `/workspace/gateway-backup/dumps/` | Daily `pg_dump -Fc`, newest 7 |
| `/workspace/gateway-backup/OWNER` | The pod ID allowed to write here |
| `/workspace/gateway-backup/status/` | `last-cycle`, `last-base-backup`, `last-dump`, `last-purge`, `last-restore` |

Schedule: a base backup after every fresh init and restore. A daily cycle runs at most 24 h after
the previous one: a base backup, a dump, retention and the call-log purge. Retention keeps the
newest 3 base backups plus any younger than 3 days, the newest 7 dumps, and the WAL from the
oldest kept base backup on. Backups at rest are not encrypted (spec §8).
