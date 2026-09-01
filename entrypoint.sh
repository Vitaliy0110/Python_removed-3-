#!/bin/sh
set -e

echo "Waiting for database at ${DB_HOST}:${DB_PORT}..."
until nc -z "${DB_HOST}" "${DB_PORT}"; do
  sleep 0.5
done
echo "Database is up."

python manage.py migrate --noinput
python manage.py collectstatic --noinput

# daphne — ASGI-сервер, нужен для WebSocket (/ws/comments/).
# 'daphne runserver' для разработки НЕ подходит для продакшена — тут используем
# сам daphne напрямую, как рекомендует документация Django Channels.
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application