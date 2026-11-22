#!/usr/bin/env bash
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

case "$1" in
    auth) PUERTO=8001 ;;
    music) PUERTO=8002 ;;
    party) PUERTO=8003 ;;
    queue) PUERTO=8004 ;;
    streaming) PUERTO=8005 ;;
    logs) PUERTO=8006 ;;
    *) echo "Uso: ./partyearsBackend.sh <auth|music|party|queue|streaming|logs>" >&2; exit 1 ;;
esac

# venv instead of .venv: .venv is the Windows one (partyearsBackend.ps1) and a disk shared
# between both systems would mix them.
if [ ! -d venv ]; then
    python3 -m venv venv
fi
venv/bin/pip install -q -r requirements.txt

# Migrations by hand instead of on every start: the dev database is shared, so a branch's
# unmerged migrations would reach everyone (README section 6).
# 0.0.0.0 instead of 127.0.0.1: phones and other PCs on the network must reach the service.
DJANGO_SETTINGS_MODULE="config.settings.$1" exec venv/bin/python manage.py runserver "0.0.0.0:$PUERTO"
