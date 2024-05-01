"""Listener for the server."""

import logging
import os
from socket import AF_INET, SHUT_RDWR, SO_REUSEADDR, SOCK_STREAM, SOL_SOCKET, socket
from types import UnionType
from typing import get_args, overload

from pydantic import BaseModel

from client.common import DeterminationT, expect, read_message, send_model
from client.const import EXIT_TIMEOUT
from client.typedefs import (
    AckMessage,
    AnyCommands,
    AnyResult,
    FinMessage,
    NopMessage,
    ShellResult,
    SynMessage,
)
from server.common import env_bool
from server.const import INITIAL_COMMANDS
from server.llama_chat import LlamaChat
from server.terminal import Terminal

log = logging.getLogger(__name__)


class Server(BaseModel):
    """Listener for the server."""

    _initialized: bool = False
    _socket: socket | None = None
    _llama: LlamaChat
    _data: bytes = b''
    _terminal: Terminal
    _prompt: str | None = None
    _intro_done: bool = False

    def __init__(self, llama: LlamaChat, terminal: Terminal):
        """Initialize the server."""
        super().__init__()
        log.info('Starting the server')
        sock = socket(AF_INET, SOCK_STREAM)
        sock.bind(('127.0.0.1', int(os.getenv('POCKET_ASI_PORT', '1199'))))
        sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        sock.listen()
        log.info(f'Listening on port {sock.getsockname()[1]}')
        self._socket = sock
        self._llama = llama
        self._terminal = terminal

    def serve(self):
        """Serve the server."""
        while self._socket:
            try:
                self._handle_connection()
            except ConnectionError as e:
                log.warning('Connection closed')
                log.debug(e)

    def cleanup(self):
        """Close the server."""
        log.info('Closing the server')
        if self._socket is not None:
            try:
                self._socket.shutdown(SHUT_RDWR)
                self._socket.close()
                self._socket = None
            except OSError:
                log.info('Server already closed')

    def _handle_connection(self):
        log.info('Waiting for connection')
        if self._socket is None:
            _err = 'Socket is closed'
            raise ConnectionError(_err)
        conn, _ = self._socket.accept()
        timeout = EXIT_TIMEOUT + 1
        log.info(f'Connection accepted from {conn.getpeername()} with timeout {timeout}s')
        with conn:
            conn.settimeout(timeout)
            _ = self._expect(conn, SynMessage | NopMessage)
            if isinstance(_, NopMessage):
                log.info('Received NOP, closing connection')
                return
            log.debug(f'Received SYN from {conn.getpeername()}')
            send_model(conn, AckMessage())
            _ = self._expect(conn, AckMessage)
            log.debug(f'Received ACK from {conn.getpeername()}, connection established')

            if not self._intro_done:
                self._initial_commands(conn)
            self._intro_done = True
            while True:
                try:
                    commands = self._llama.get_commands()
                except ValueError:
                    continue
                try:
                    self._send_commands(conn, commands)
                except ConnectionError:
                    break
            log.info('Connection closed')

    def _initial_commands(self, conn: socket):
        """Run initial commands."""
        if not env_bool('LLAMA_SHOW_INTRO'):
            self._terminal.suspended = True
        if not self._initialized:
            self._send_commands(conn, INITIAL_COMMANDS)
            self._initialized = True
        self._terminal.suspended = False

    @overload
    def _expect(self, conn: socket, what: type[UnionType]) -> AnyResult: ...
    @overload
    def _expect(self, conn: socket, what: type[DeterminationT]) -> DeterminationT: ...

    def _expect(self, conn: socket, what):
        """Expect a message type."""
        message = expect(read_message(conn), what, log.debug)
        if message in get_args(FinMessage):
            log.warning(f'Received FIN from {conn.getpeername()}')
            self.cleanup()
            _err = 'FIN received'
            raise ConnectionError(_err)
        return message

    def _send_commands(
        self,
        conn: socket,
        llm_commands: AnyCommands,
    ) -> None:
        """Send commands to the connection."""
        results: list[AnyResult] = []
        for command in llm_commands.root:
            send_model(conn, command)
            if self._terminal.stream:
                self._terminal.render_prompt(command=command)
            result = self._expect(conn, AnyResult)
            results.append(result)
            log.debug(f'Rendering result: {result}')
            self._terminal.render(self._prompt, result, command.comment)
            if isinstance(result, ShellResult):
                self._prompt = result.prompt.prompt
        # Done after the loop to ensure that all commands were successfully executed
        # This should only be an issue if the client disconnects, which would indicate a problem
        # that likely means we should forget that part of the history
        self._llama.append_commands(results)
