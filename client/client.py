"""Client for the Llama connection."""

import logging
import os
import time
from socket import AF_INET, SHUT_RDWR, SOCK_STREAM, socket
from types import UnionType
from typing import get_args, overload

from pydantic import BaseModel

from client.common import DeterminationT, expect, read_message, send_model
from client.const import RECONNECT_DELAY
from client.shell import Shell
from client.typedefs import (
    AckMessage,
    AnyResult,
    AnyServerRuntimeMessage,
    FinMessage,
    SynMessage,
)

log = logging.getLogger(__name__)


class Client(BaseModel):
    """Client for the Llama connection."""

    _shell: Shell
    _data: bytes = b''
    _socket: socket | None = None

    def __init__(self, shell: Shell) -> None:
        """Initialize the client."""
        super().__init__()
        self._shell = shell

    def connect(self) -> None:
        """Connect to the Llama server."""
        while True:
            try:
                self._handle_connection()
            except ConnectionError as e:
                log.warning('Connection closed')
                log.debug(e)
            self._socket = None
            log.info(f'Waiting {RECONNECT_DELAY}s before reconnecting')
            time.sleep(RECONNECT_DELAY)

    def cleanup(self) -> None:
        """Close the client."""
        try:
            if self._socket:
                self._socket.shutdown(SHUT_RDWR)
                self._socket.close()
                self._socket = None
        except OSError:
            log.info('Socket already closed')

    def _handle_connection(self) -> None:
        """Connect to the Llama server."""
        port = int(os.getenv('LLAMA_PORT', '1199'))

        with socket(AF_INET, SOCK_STREAM) as self._socket:
            log.info(f'Connecting to host.docker.internal:{port}')
            self._socket.settimeout(1)
            self._socket.connect(('host.docker.internal', port))

            send_model(self._socket, SynMessage())
            _ = self._expect(AckMessage)
            send_model(self._socket, AckMessage())
            log.info('Connected to server')

            self._socket.settimeout(None)
            try:
                self._handle_commands()
            except ConnectionError:
                log.exception('Connection closed')
        self._socket = None

    @overload
    def _expect(self, what: type[UnionType]) -> AnyResult: ...
    @overload
    def _expect(self, what: type[DeterminationT]) -> DeterminationT: ...

    def _expect(self, what):
        """Expect a message type."""
        message = expect(read_message(self._socket), what, log.debug)
        if message in get_args(FinMessage):
            _err = 'FIN received'
            log.warning(_err)
            self.cleanup()
            raise ConnectionError(_err)
        return message

    def _handle_commands(self) -> None:
        """Handle commands from the server."""
        while True:
            command = self._expect(AnyServerRuntimeMessage)
            if isinstance(command, FinMessage):
                log.warning('Received FIN from server')
                self.cleanup()
                _err = 'Connection closed'
                raise ConnectionError(_err)
            result = self._shell.execute(command)
            log.debug(f'Sending result: {result}')
            send_model(self._socket, result)
