#!/bin/bash

echo "Waiting for postgres..."
while ! nc -z db 5432; do
  sleep 0.1
done
echo "PostgreSQL started"

# Run migrations
python3 manage.py makemigrations
python3 manage.py migrate

# Collect static
python3 manage.py collectstatic --no-input --clear

exec "$@"