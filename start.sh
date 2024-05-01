#!/bin/bash

set -eEuo pipefail

_log() {
    echo "[$(date -Iseconds)] [start.sh] $1" > /dev/stderr
}

_message() {
    echo "{\"meta\": \"$1\"}" | nc localhost "${LLAMA_PORT:-1199}"
}

_expect_code() {
    RET="$?"
    case $1 in
        SIGINT)  SIGNUM=2 ;;
        SIGTERM) SIGNUM=15 ;;
        *)       _log "Invalid signal $1"; exit 1 ;;
    esac
    EXPECTED="$((128 + SIGNUM))"
    if [ "$RET" -ne "${EXPECTED}" ]; then
        _log "Expected exit code $1 (${EXPECTED}), got ${RET}"
        exit 1
    else
        _log "Exited cleanly with code $1"
    fi
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

while ! _message NOP; do
    _log "Waiting for server to start"
    sleep 1
done

_log "Starting client"
docker compose down
docker compose up --build || _expect_code SIGINT

_message FIN || _log "Failed to send FIN"

_log "Client exited, stopping server"
kill $PID || _log "Server already stopped"
wait $PID || _expect_code SIGTERM
_log "Server stopped"
