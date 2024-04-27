"""Main entrypoint for the application."""

from coloredlogs import logging

from client.client import Client
from client.shell import Shell

log = logging.getLogger(__name__)


def run() -> None:
    """Run the application."""
    log.info('Starting application')
    shell = Shell()
    client = Client(shell)

    client.connect()
