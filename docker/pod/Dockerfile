# Pod-only image (spec §3.2): the gateway, PostgreSQL 17 and its backups in one container, because
# a Runpod pod runs one image. Staging keeps docker/web/Dockerfile + nginx; nothing there uses this.
# bookworm, not trixie: PGDG's postgresql-17 for bookworm needs libicu72.
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PATH="/usr/lib/postgresql/17/bin:${PATH}" \
    PGDATA=/var/lib/postgresql/gateway

# postgresql-common first, so its createcluster.conf can turn off the unused default cluster
# before postgresql-17 installs. procps gives pkill (Runpod crash drill).
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && install -d /usr/share/postgresql-common/pgdg \
 && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
 && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends postgresql-common \
 && sed -ri 's/^#?\s*create_main_cluster\s*=.*/create_main_cluster = false/' /etc/postgresql-common/createcluster.conf \
 && apt-get install -y --no-install-recommends postgresql-17 supervisor gosu procps \
 && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

COPY ./requirements.txt /usr/src/app/
WORKDIR /usr/src/app/
RUN pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r requirements.txt

COPY . /usr/src/app/

RUN chmod +x docker/pod/entrypoint.sh docker/pod/app-start.sh docker/pod/archive-wal.sh \
        docker/pod/restore-wal.sh docker/pod/backup-loop.sh \
        docker/pod/backup-status docker/pod/backup-reset docker/pod/gateway-manage \
 && ln -s /usr/src/app/docker/pod/backup-status /usr/local/bin/backup-status \
 && ln -s /usr/src/app/docker/pod/backup-reset /usr/local/bin/backup-reset \
 && ln -s /usr/src/app/docker/pod/gateway-manage /usr/local/bin/gateway-manage \
 && test ! -e /var/lib/postgresql/17/main \
 && for tool in initdb pg_ctl pg_controldata pg_basebackup pg_archivecleanup pg_dump pg_isready psql \
        supervisord gosu mountpoint cmp gzip tar pkill; do \
        command -v "$tool" >/dev/null || { echo "missing: $tool"; exit 1; }; \
    done

EXPOSE 8000
ENTRYPOINT ["/usr/src/app/docker/pod/entrypoint.sh"]
