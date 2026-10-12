#!/bin/bash
# Supervised app program (spec §7.2): wait for the in-pod Postgres, migrate, collect static files
# (ServeStaticMiddleware serves them; the pod has no nginx), then gunicorn with uvicorn workers.
set -euo pipefail
cd /usr/src/app

echo "[app] waiting for Postgres on 127.0.0.1:${POSTGRES_PORT}"
until pg_isready -q -h 127.0.0.1 -p "${POSTGRES_PORT}"; do sleep 1; done

python manage.py migrate --noinput
python manage.py collectstatic --noinput --clear

# --graceful-timeout 3: requests still running 3 s after SIGTERM are cut (spec §6).
# No --access-logfile: it would print unredacted access lines (same as staging).
exec gunicorn -k uvicorn_worker.UvicornWorker -w "${GUNICORN_WORKERS:-2}" -b 0.0.0.0:8000 \
  --timeout 300 --graceful-timeout 3 ai4deliberation_backend.asgi:application
