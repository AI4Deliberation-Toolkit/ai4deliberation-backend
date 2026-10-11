#!/bin/bash
set -euo pipefail

echo "Waiting for postgres..."
while ! nc -z "${POSTGRES_HOST:-db}" "${POSTGRES_PORT:-5432}"; do
  sleep 0.1
done
echo "PostgreSQL started"

echo "Running migrations..."
python3 manage.py migrate --noinput

echo "Collecting static files..."
python3 manage.py collectstatic --no-input --clear

exec "$@"
