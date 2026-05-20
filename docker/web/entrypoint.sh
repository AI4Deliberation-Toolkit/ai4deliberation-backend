#!/bin/bash
set -euo pipefail

echo "Waiting for postgres..."
while ! nc -z db 5432; do
  sleep 0.1
done
echo "PostgreSQL started"

echo "Running migrations..."
python3 manage.py migrate --noinput

echo "Seeding taxonomy from code..."
python3 manage.py seed_taxonomy

echo "Validating translation coverage..."
python3 manage.py validate_taxonomy

echo "Collecting static files..."
python3 manage.py collectstatic --no-input --clear

exec "$@"
