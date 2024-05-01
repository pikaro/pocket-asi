"""Main entrypoint for the application."""

import atexit
import signal
import sys

from coloredlogs import logging

from client.client import Client
from client.shell import Shell

log = logging.getLogger(__name__)


def run() -> None:
    """Run the application."""
    log.info('Starting application')
    shell = Shell()
    client = Client(shell)

    @atexit.register
    def _cleanup():
        log.info('Cleaning up')
        client.cleanup()

    def _signal_handler(sig, frame):
        _ = frame
        log.info(f'Received signal {sig}, cleaning up')
        client.cleanup()
        sys.exit(0)

    _ = signal.signal(signal.SIGINT, _signal_handler)
    _ = signal.signal(signal.SIGTERM, _signal_handler)

    client.connect()
