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

    shell: subprocess.Popen
    stdin: IO
    q_stdout: Queue[OutputLine]
    q_stderr: Queue[OutputLine]

    def __init__(self):
        """Create shell process and streams."""
        self.shell = subprocess.Popen(
            ['/bin/sh'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if not self.shell.stdout or not self.shell.stdin or not self.shell.stderr:
            _err = 'Shell streams are not available'
            raise ValueError(_err)

        self.stdin = self.shell.stdin
        self.q_stdout = Queue()
        self.q_stderr = Queue()
        self.thread_stdout = threading.Thread(
            target=enqueue_output, args=(self.shell.stdout, self.q_stdout)
        )
        self.thread_stderr = threading.Thread(
            target=enqueue_output, args=(self.shell.stderr, self.q_stderr)
        )
        self.thread_stdout.daemon = True
        self.thread_stderr.daemon = True
        self.thread_stdout.start()
        self.thread_stderr.start()

    def _put_stdin(self, command: str) -> None:
        """Execute a command in the shell."""
        _ = self.stdin.write(command.encode('utf-8') + b'\n')
        self.stdin.flush()

    def _get_stdout(self) -> list[OutputLine]:
        """Get the stdout from the shell."""
        stdout = list(self.q_stdout.queue)
        self.q_stdout.queue.clear()
        return stdout

    def _get_stderr(self) -> list[OutputLine]:
        """Get the stderr from the shell."""
        stderr = list(self.q_stderr.queue)
        self.q_stderr.queue.clear()
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
