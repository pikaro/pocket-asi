"""Listener for the server."""

import logging
import os
from socket import AF_INET, SOCK_STREAM, socket

from pydantic import BaseModel, ValidationError

from client.const import EXIT_TIMEOUT
from client.typedefs import CommandResult
from server.const import INITIAL_COMMANDS
from server.llama_chat import LlamaChat
from server.terminal import Terminal
from server.typedefs import LlmCommands

log = logging.getLogger(__name__)


class Server(BaseModel):
    """Listener for the server."""

    _initialized: bool = False
    _socket: socket
    _llama: LlamaChat
    _data: bytes = b''
    _terminal: Terminal
    _prompt: str | None = None

    def __init__(self, llama: LlamaChat, terminal: Terminal):
        """Initialize the server."""
        super().__init__()
        log.info('Starting the server')
        sock = socket(AF_INET, SOCK_STREAM)
        sock.bind(('127.0.0.1', int(os.getenv('POCKET_ASI_PORT', '1199'))))
        sock.listen()
        log.info(f'Listening on port {sock.getsockname()[1]}')
        self._socket = sock
        self._llama = llama
        self._terminal = terminal

    def serve(self):
        """Serve the server."""
        while True:
            self._handle_connection()

    def cleanup(self):
        """Close the server."""
        log.info('Closing the server')
        try:
            self._socket.close()
        except OSError:
            log.info('Server already closed')

    def _handle_connection(self):
        log.info('Waiting for connection')
        conn, _ = self._socket.accept()
        timeout = EXIT_TIMEOUT + 1
        log.info(f'Connection accepted from {conn.getpeername()} with timeout {timeout}s')
        with conn:
            conn.settimeout(timeout)
            self._initial_commands(conn)
            while True:
                try:
                    commands = self._llama.get_commands()
                except ValidationError:
                    continue
                try:
                    self._send_commands(conn, commands)
                except ConnectionError:
                    break
        log.info('Connection closed')

    def _initial_commands(self, conn: socket):
        """Run initial commands."""
        if not self._initialized:
            commands = LlmCommands(commands=INITIAL_COMMANDS, comment='Initial commands')
            self._send_commands(conn, commands)
            self._initialized = True

    def _read_message(self, conn: socket) -> CommandResult:
        """Read a message from the connection."""
        while True:
            data = conn.recv(4096)
            if not data:
                _err = 'Connection closed'
                raise ConnectionError(_err)
            self._data += data
            if b'\0' in self._data:
                message, self._data = self._data.split(b'\0', 1)
                result_json = message.decode('utf-8')
                return CommandResult.model_validate_json(result_json)

    def _send_commands(
        self,
        conn: socket,
        llm_commands: LlmCommands,
    ) -> None:
        """Send commands to the connection."""
        comment = llm_commands.comment
        commands = llm_commands.commands
        for i, command in enumerate(commands):
            self._send_command(conn, command)
            if self._terminal.stream:
                self._terminal.render_prompt(command=command)
            result = self._read_message(conn)
            self._llama.append_command(result)
            _comment = f'{comment} ({i + 1}/{len(commands)})' if comment else None
            self._terminal.render(self._prompt, result, _comment)
            self._prompt = result.prompt.prompt

    def _send_command(self, conn: socket, command: str):
        """Send a command to the connection."""
        conn.sendall(f'{command}\0'.encode())
