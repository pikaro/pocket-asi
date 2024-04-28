"""Entrypoint for the server."""

import atexit
import logging

from client.typedefs import LlamaClientConfig
from server.llama_server import LlamaServer
from server.server import Server
from server.terminal import Terminal
from server.typedefs import LlamaServerConfig

from .llama_chat import LlamaChat

log = logging.getLogger(__name__)


def run():
    """Run the server."""
    log.info('Starting server')

    server_config = LlamaServerConfig()
    client_config = LlamaClientConfig()

    llama_server = LlamaServer(server_config=server_config, client_config=client_config)
    llama_chat = LlamaChat(llama_server)

    terminal_stream = True
    if llama_server.client_config.stream:
        log.warning('Llama is streaming, disabling terminal stream')
        terminal_stream = False
    if llama_server.server_config.verbose:
        log.warning('Llama is verbose, disabling terminal stream')
        terminal_stream = False
    if log.getEffectiveLevel() <= logging.DEBUG:
        log.warning('Debug logging enabled, disabling terminal stream')
        terminal_stream = False

    terminal = Terminal(stream=terminal_stream)
    server = Server(llama_chat, terminal)

    @atexit.register
    def _cleanup():
        log.info('Cleaning up')
        server.cleanup()

    server.serve()
