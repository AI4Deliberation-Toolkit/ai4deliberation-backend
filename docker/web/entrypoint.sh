#!/bin/bash
set -euo pipefail

echo "Pre-flight: checking disk headroom for HF model cache..."
mkdir -p /root/.cache/huggingface
MIN_FREE_GB=3
AVAILABLE_KB=$(df -P /root/.cache/huggingface | awk 'NR==2 {print $4}')
AVAILABLE_GB=$((AVAILABLE_KB / 1024 / 1024))
if [ "$AVAILABLE_GB" -lt "$MIN_FREE_GB" ]; then
    echo "FATAL: only ${AVAILABLE_GB}G free in /root/.cache/huggingface; need >= ${MIN_FREE_GB}G for model downloads. Free disk and retry." >&2
    exit 1
fi
echo "Disk headroom OK: ${AVAILABLE_GB}G free in /root/.cache/huggingface"

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
