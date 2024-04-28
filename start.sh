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

if [ ! -f .env ]; then
    _log "Creating .env file"
    cp .env.example .env
fi

if [ ! -d workspace ]; then
    _log "Creating workspace directory"
    ./reset.sh
fi

set -a
source .env
set +a

if [ "${LLAMA_MODEL_PATH:-undefined}" = "undefined" ]; then
    _log "Configure your model path in .env!"
    exit 1
fi

_log "Installing dependencies"
poetry install

_log "Starting server"
python3 server.py &
PID=$!
_log "Server started with PID $PID"

while ! nc -z localhost "${LLAMA_PORT:-1199}"; do
    _log "Waiting for server to start"
    sleep 1
done

_log "Starting client"
docker compose down
docker compose up --build

_log "Client exited, stopping server"
kill $PID
wait $PID
_log "Server stopped"
