"""Entrypoint for the server."""

import atexit
import logging

from server.llama_server import LlamaServer
from server.server import Server
from server.terminal import Terminal

from .llama_chat import LlamaChat

log = logging.getLogger(__name__)


def run():
    """Run the server."""
    log.info('Starting server')
    llama_server = LlamaServer()
    llama_chat = LlamaChat(llama_server)
    terminal = Terminal()
    server = Server(llama_chat, terminal)

    @atexit.register
    def _cleanup():
        log.info('Cleaning up')
        server.cleanup()

    server.serve()
