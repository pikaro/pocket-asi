"""Interactive shell."""

import re
import subprocess
import threading
import time
from pathlib import Path
from queue import Queue
from typing import IO, cast

import bashlex
import inotify_simple
from coloredlogs import logging
from pydantic import BaseModel

# from immutable.const import SHELL_CONTAINER_NODE_TYPES
from immutable.typedefs import CommandResult, OutputLine, Ps1

log = logging.getLogger(__name__)


def enqueue_output(out: IO, queue: Queue[OutputLine]) -> None:
    """Enqueue output from a stream."""
    for line in iter(out.readline, b''):
        queue.put((time.time(), line.decode('utf-8')))
    out.close()


EXIT_FILE = '/tmp/exit_code'  # noqa: S108
EXIT_TIMEOUT = 1000


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
            ['/bin/sh'],
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
        # PS1: '$? \u@\h:\w # '
        match = re.match(
            r'^(?P<exit_code>[0-9]+) (?P<user>.+)@(?P<host>.+):(?P<cwd>.+) (?P<usertype>[$#]) $',
            ps1,
        )
        if not match:
            _err = 'PS1 prompt does not match expected format'
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

    def _wait_done(self) -> str:
        """Wait for the shell to finish."""
        inotify = inotify_simple.INotify()
        i_watch = inotify.add_watch(EXIT_FILE, inotify_simple.flags.CREATE)
        ret = inotify.read(timeout=EXIT_TIMEOUT)
        inotify.rm_watch(i_watch)
        if not list(ret):
            _err = 'Shell did not finish in time'
            raise TimeoutError(_err)
        exit_file = Path(EXIT_FILE)
        ps1 = exit_file.read_text(encoding='utf-8')
        exit_file.unlink(missing_ok=True)
        return ps1

    def run(self, command: str) -> CommandResult:
        """Run a command in the shell."""
        self._lex(command)
        self._put_stdin(command)
        self._put_stdin(f'echo $PS1 > {EXIT_FILE}')
        ret = self._wait_done()
        ps1 = self._parse_ps1(ret)
        stdout = self._get_stdout()
        stderr = self._get_stderr()
        return CommandResult(
            command=command,
            stdout=stdout,
            stderr=stderr,
            exit_code=ps1['exit_code'],
            ps1=ps1,
        )
