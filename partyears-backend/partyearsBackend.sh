#!/usr/bin/env bash
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

declare -A PUERTOS=([auth]=8001 [music]=8002 [party]=8003 [queue]=8004 [streaming]=8005 [logs]=8006)

if [ -z "$1" ] || { [ "$1" != todos ] && [ -z "${PUERTOS[$1]:-}" ]; }; then
    echo "Uso: ./partyearsBackend.sh <auth|music|party|queue|streaming|logs|todos>" >&2
    exit 1
fi

# venv instead of .venv: .venv is the Windows one (partyearsBackend.ps1) and a disk shared
# between both systems would mix them.
if [ ! -d venv ]; then
    python3 -m venv venv
fi
venv/bin/pip install -q -r requirements.txt

# Migrations by hand instead of on every start: the dev database is shared, so a branch's
# unmerged migrations would reach everyone (README section 6).
# 0.0.0.0 instead of 127.0.0.1: phones and other PCs on the network must reach the service.
if [ "$1" != todos ]; then
    DJANGO_SETTINGS_MODULE="config.settings.$1" exec venv/bin/python manage.py runserver "0.0.0.0:${PUERTOS[$1]}"
fi

# todos: what a party needs on this machine, in one terminal. Each line is tagged with its
# service; Ctrl+C stops them all (kill 0 reaches the whole process group, including the
# children that runserver's autoreloader starts).
trap 'trap - INT TERM EXIT; kill 0' INT TERM EXIT

con_etiqueta() {
    local etiqueta=$1
    shift
    "$@" 2>&1 | sed -u "s/^/[$etiqueta] /" &
}

for servicio in auth music party queue; do
    con_etiqueta "$servicio" env DJANGO_SETTINGS_MODULE="config.settings.$servicio" \
        venv/bin/python manage.py runserver --noreload "0.0.0.0:${PUERTOS[$servicio]}"
done

# Event workers only when their RabbitMQ URL is in .env: without them the party still works,
# the events wait in the outbox (README section 6.1).
tiene() { grep -qE "^$1=.+" .env 2>/dev/null; }
if tiene PARTY_RABBITMQ_URL; then
    con_etiqueta party-eventos env DJANGO_SETTINGS_MODULE=config.settings.party \
        venv/bin/python manage.py publicar_eventos
fi
if tiene QUEUE_RABBITMQ_URL; then
    con_etiqueta queue-eventos env DJANGO_SETTINGS_MODULE=config.settings.queue \
        venv/bin/python manage.py publicar_eventos
fi
if tiene LOGS_RABBITMQ_URL; then
    con_etiqueta logs-eventos env DJANGO_SETTINGS_MODULE=config.settings.logs \
        venv/bin/python manage.py consumir_eventos
fi

echo "Backend corriendo. Ctrl+C para detener todo."
wait
