"""Interactive shell."""

import os
import re
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager, suppress
from pathlib import Path
from queue import Queue
from select import select
from typing import IO, cast

import bashlex
from coloredlogs import logging
from pydantic import BaseModel

from immutable.common import random_string

# from immutable.const import SHELL_CONTAINER_NODE_TYPES
from immutable.typedefs import CommandResult, OutputLine, Ps1

log = logging.getLogger(__name__)


def enqueue_output(out: IO, queue: Queue[OutputLine]) -> None:
    """Enqueue output from a stream."""
    for line in iter(out.readline, b''):
        queue.put((time.time(), line.decode('utf-8')))
    out.close()


EXIT_TIMEOUT = 1.0


@contextmanager
def temp_fifo():
    """Create a temporary FIFO."""
    tmp = Path(tempfile.mkdtemp())
    fifo = tmp / random_string(8)
    with suppress(FileNotFoundError):
        fifo.unlink()
    try:
        os.mkfifo(fifo)
    except OSError as e:
        _err = f'Failed to create FIFO: {e}'
        raise OSError(_err) from e
    try:
        log.debug(f'Created FIFO: {fifo}')
        yield fifo
    finally:
        fifo.unlink()
        tmp.rmdir()


class Shell(BaseModel):
    """Interactive shell."""

    _shell: subprocess.Popen
    _stdin: IO
    _q_stdout: Queue[OutputLine]
    _q_stderr: Queue[OutputLine]
    _thread_stdout: threading.Thread
    _thread_stderr: threading.Thread

    def __init__(self):
        """Create shell process and streams."""
        super().__init__()

        self._shell = subprocess.Popen(
            ['/bin/bash'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if not self._shell.stdout or not self._shell.stdin or not self._shell.stderr:
            _err = 'Shell streams are not available'
            raise ValueError(_err)

        self._stdin = self._shell.stdin
        self._q_stdout = Queue()
        self._q_stderr = Queue()
        self._thread_stdout = threading.Thread(
            target=enqueue_output, args=(self._shell.stdout, self._q_stdout)
        )
        self._thread_stderr = threading.Thread(
            target=enqueue_output, args=(self._shell.stderr, self._q_stderr)
        )
        self._thread_stdout.daemon = True
        self._thread_stderr.daemon = True
        self._thread_stdout.start()
        self._thread_stderr.start()

        log.info(f'Shell started with PID {self._shell.pid}')

    def _put_stdin(self, command: str) -> None:
        """Execute a command in the shell."""
        _ = self._stdin.write(command.encode('utf-8') + b'\n')
        self._stdin.flush()

    def _get_stdout(self) -> list[OutputLine]:
        """Get the stdout from the shell."""
        stdout = list(self._q_stdout.queue)
        self._q_stdout.queue.clear()
        return stdout

    def _get_stderr(self) -> list[OutputLine]:
        """Get the stderr from the shell."""
        stderr = list(self._q_stderr.queue)
        self._q_stderr.queue.clear()
        return stderr

    def _lex(self, command: str) -> None:
        """Lex a command."""
        _ = bashlex.parse(command)
        # TODO: Even necessary to parse the command?

    def _parse_ps1(self, ps1: str) -> Ps1:
        """Parse the PS1 prompt."""
        # $PS1: '$? \u@\h:\w # '
        match = re.match(
            r'^(?P<exit_code>[0-9]+) (?P<user>.+)@(?P<host>.+):(?P<cwd>.+) (?P<usertype>[$#]) $',
            ps1,
        )
        if not match:
            _err = f'PS1 prompt does not match expected format: {ps1}'
            raise ValueError(_err)
        groups = match.groupdict()
        return cast(
            Ps1,
            {
                'ps1': ps1,
                'exit_code': int(groups['exit_code']),
                'user': groups['user'],
                'host': groups['host'],
                'cwd': groups['cwd'],
                'usertype': groups['usertype'],
            },
        )

    def _wait_done(self, fifo: Path) -> str:
        """Wait for the shell to finish."""
        fd = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
        try:
            log.debug(f'Waiting for shell to finish in {EXIT_TIMEOUT} seconds')
            ready, _, _ = select([fd], [], [], EXIT_TIMEOUT)

            if not ready:
                _err = 'Shell did not finish in time'
                log.error(_err)
                log.error(f'Stdout: {self._get_stdout()}')
                log.error(f'Stderr: {self._get_stderr()}')
                raise TimeoutError(_err)
            return os.read(fd, 1024).decode('utf-8')
        finally:
            os.close(fd)

    def run(self, command: str) -> CommandResult:
        """Run a command in the shell."""
        self._lex(command)
        log.debug(f'Running command: {command}')
        self._put_stdin(command)
        with temp_fifo() as fifo:
            # Bash unsets PS1 on startup because it's not interactive
            ps1 = os.environ['PS1'].replace('"', '\\"')
            self._put_stdin(
                f'(R="$?"; PS1="{ps1}"; (exit "$R"); echo -n "${{PS1@P}}" >> {fifo}; exit "$R")'
            )
            ret = self._wait_done(fifo)
        ps1 = self._parse_ps1(ret)
        log.debug(f'Command exited with code {ps1["exit_code"]}')
        stdout = self._get_stdout()
        stderr = self._get_stderr()
        return CommandResult(
            command=command,
            stdout=stdout,
            stderr=stderr,
            exit_code=ps1['exit_code'],
            ps1=ps1,
        )
