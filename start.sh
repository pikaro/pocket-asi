#!/bin/bash

_log() {
    echo "[$(date -Iseconds)] [run.sh] $1" > /dev/stderr
}

if [ ! -d .venv ]; then
    _log "Creating virtual environment"
    python3 -m venv .venv
fi

_log "Activating virtual environment"
source .venv/bin/activate

_log "Installing dependencies"
poetry install

_log "Starting server"
python3 server.py &
PID=$!
_log "Server started with PID $PID"

_log "Starting client"
docker compose down
docker compose up --build

_log "Client exited, stopping server"
kill $PID
wait $PID
_log "Server stopped"
