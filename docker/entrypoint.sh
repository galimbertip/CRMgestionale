#!/bin/sh
set -e
python manage.py migrate --noinput
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  python manage.py createsuperuser --noinput 2>/dev/null || true
fi
exec "$@"
