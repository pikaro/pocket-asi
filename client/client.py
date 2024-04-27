"""Client for the Llama connection."""

import logging
import os
from socket import AF_INET, SOCK_STREAM, socket

from pydantic import BaseModel

from client.shell import Shell
from client.typedefs import CommandResult

log = logging.getLogger(__name__)


class Client(BaseModel):
    """Client for the Llama connection."""

    _shell: Shell
    _data: bytes = b''

    def __init__(self, shell: Shell) -> None:
        """Initialize the client."""
        super().__init__()
        self._shell = shell

    def connect(self) -> None:
        """Connect to the Llama server."""
        port = int(os.getenv('LLAMA_PORT', '1199'))

        while True:
            with socket(AF_INET, SOCK_STREAM) as sock:
                log.info(f'Connecting to host.docker.internal:{port}')
                sock.connect(('host.docker.internal', port))
                try:
                    self._handle_commands(sock)
                except ConnectionError:
                    log.exception('Connection closed')

    def _handle_commands(self, sock: socket) -> None:
        """Handle commands from the server."""
        while True:
            command = self._read_command(sock)
            log.debug(f'Received command: {command}')
            result = self._shell.execute(command)
            log.debug(f'Sending result: {result}')
            self._send_result(sock, result)

    def _read_command(self, sock: socket) -> str:
        """Read a command from the server."""
        while True:
            self._data += sock.recv(1024)
            if not self._data:
                _err = 'Connection closed'
                raise ConnectionError(_err)
            if b'\0' in self._data:
                message, self._data = self._data.split(b'\0', 1)
                return message.decode('utf-8')

    def _send_result(self, sock: socket, message: CommandResult) -> None:
        """Send a result to the server."""
        sock.sendall(message.model_dump_json().encode('utf-8') + b'\0')
