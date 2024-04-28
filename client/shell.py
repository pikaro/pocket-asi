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
from typing import IO, overload

import bashlex
import bashlex.ast
import bashlex.errors
import psutil
from bashlex.errors import ParsingError
from coloredlogs import logging
from pydantic import BaseModel, ValidationError

from client.common import colored, log_output, random_string
from client.const import (
    COLORS,
    EXIT_TIMEOUT,
    GENERIC_ERRORS,
    KILL_TIMEOUT,
    LEXER_ERRORS,
    SHELL_INTERACTIVE_COMMANDS,
    USERTYPES,
)
from client.typedefs import (
    AnyCommand,
    AnyFileCommand,
    AnyFileResult,
    AnyResult,
    BaseResult,
    FileReadCommand,
    FileReadResult,
    FileWriteCommand,
    FileWriteResult,
    LlamaClientConfig,
    OutputLine,
    Prompt,
    ShellCommand,
    ShellResult,
)

log = logging.getLogger(__name__)


def _dummy_out(message: str) -> list[OutputLine]:
    """Dummy output function."""
    return [(time.time(), f'/bin/bash: {message}')]


def _enqueue_output(out: IO, queue: Queue[OutputLine]) -> None:
    """Enqueue output from a stream."""
    for line in iter(out.readline, b''):
        queue.put((time.time(), line.decode('utf-8')))
    out.close()


def _kill_procs(procs: list[psutil.Process], kill: bool = False) -> bool:
    """Kill the shell children."""
    method = 'kill' if kill else 'terminate'
    log.warning(f'Will {method} {len(procs)} processes')
    for proc in procs:
        with suppress(psutil.NoSuchProcess):
            getattr(proc, method)()
    if not kill:
        gone, alive = psutil.wait_procs(procs, timeout=KILL_TIMEOUT)
        if alive:
            log.error(f'Failed to terminate {len(alive)}/{len(procs)} processes')
        else:
            log.debug(f'Terminated {len(gone)} processes')
        return not alive
    return True


def _get_commands(command: str) -> list[str]:
    """Get the nodes of a command."""
    parsed = bashlex.parse(command)

    class _NodeVisitor(bashlex.ast.nodevisitor):
        commands: list[bashlex.ast.node]

        def __init__(self, commands: list[bashlex.ast.node]):
            super().__init__()
            self.commands = commands

        def visitcommand(self, n: bashlex.ast.node, parts: list[bashlex.ast.node]) -> None:
            _ = parts
            self.commands.append(n)

    commands = []
    visitor = _NodeVisitor(commands)
    for elem in parsed:
        visitor.visit(elem)

    return [v.parts[0].word for v in commands]


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
        self._open_shell()
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

    def _dummy_result(
        self,
        command: str,
        exit_code: int,
        stdout: str | None = None,
        stderr: str | None = None,
    ) -> ShellResult:
        """Dummy result function."""
        log.debug(
            f'Dummy result for command: {colored(command, COLORS.prompt)}'
            f' with exit code {exit_code}'
        )
        _ = self._ensure_shell()
        prompt = self._parse_prompt(self._get_prompt())
        system, goal, config = self._get_config()
        return ShellResult(
            command=ShellCommand(command=command),
            stdout=_dummy_out(stdout) if stdout else [],
            stderr=_dummy_out(stderr) if stderr else [],
            exit_code=exit_code,
            prompt=prompt,
            system=system,
            goal=goal,
            config=config,
        )

    def _lex(self, command: str) -> None | ShellResult:
        """Lex a command."""
        if re.sub(r'^#.*', '', command).strip() == '':
            return self._dummy_result(command, 0)
        exc: tuple[int, str] | None = None
        try:
            _ = bashlex.parse(command)
        except ParsingError as e:
            if type(e) in LEXER_ERRORS:
                exc = LEXER_ERRORS[type(e)], e.message
            else:
                raise
        except Exception as e:
            if type(e) in GENERIC_ERRORS:
                exc = GENERIC_ERRORS[type(e)]
            else:
                raise
        if exc:
            return self._dummy_result(command, exc[0], stderr=exc[1])
        commands = _get_commands(command)
        interactive = ', '.join(set(commands) & set(SHELL_INTERACTIVE_COMMANDS))
        if interactive:
            _err = f'Not a terminal: {interactive}'
            return self._dummy_result(command, -3, stderr=_err)

        return None

    def _parse_prompt(self, prompt: str) -> Prompt:
        """Parse the prompt."""
        # $PS1: '$? \u@\h:\w # '
        match = re.match(
            r'^(?P<exit_code>[0-9]+) (?P<user>.+)@(?P<host>.+):(?P<cwd>.+) (?P<usertype>[$#]) $',
            prompt,
        )
        if not match:
            _err = f'Prompt does not match expected format: {prompt}'
            raise ValueError(_err)
        groups = match.groupdict()
        return Prompt.model_validate(
            {
                'prompt': prompt,
                'exit_code': int(groups['exit_code']),
                'user': groups['user'],
                'host': groups['host'],
                'cwd': groups['cwd'],
                'usertype': USERTYPES[groups['usertype']],
            }
        )

    def _open_shell(self):
        """Open a shell."""
        log.info('Opening shell')
        self._shell = subprocess.Popen(
            ['/bin/bash'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid,  # noqa: PLW1509 (unsafe in threads -> not used in thread)
        )

        if self._streams_gone():
            _err = 'Shell streams are not available'
            raise ValueError(_err)
        assert self._shell.stdin is not None

        self._stdin = self._shell.stdin
        self._q_stdout = Queue()
        self._q_stderr = Queue()
        self._thread_stdout = threading.Thread(
            target=_enqueue_output, args=(self._shell.stdout, self._q_stdout)
        )
        self._thread_stderr = threading.Thread(
            target=_enqueue_output, args=(self._shell.stderr, self._q_stderr)
        )
        self._thread_stdout.daemon = True
        self._thread_stderr.daemon = True
        self._thread_stdout.start()
        self._thread_stderr.start()
        log.info(f'Shell started with PID {self._shell.pid}')

    def _shell_gone(self) -> bool:
        """Check if the shell is gone."""
        return self._shell.poll() is not None or not self._shell.stdin

    def _streams_gone(self) -> bool:
        """Check if the shell streams are gone."""
        return not self._shell.stdout or not self._shell.stdin or not self._shell.stderr

    def _wait_shell(self) -> None:
        """Wait for the shell to finish."""
        _ = self._shell.wait()
        self._thread_stdout.join()
        self._thread_stderr.join()
        stdout = self._get_stdout()
        stderr = self._get_stderr()
        if stdout:
            log.warning(f'Leftover stdout: {stdout}')
        if stderr:
            log.warning(f'Leftover stderr: {stderr}')
        log.info('Shell finished')

    def _close_shell(self, kill: bool = False) -> bool:
        """Close the shell."""
        log.warning(f'Closing shell with kill={kill}')
        if self._shell.poll() is None:
            gone = self._kill_shell_children(kill=kill)
            if not gone:
                log.error('Failed to kill shell children')
                return False
            shell = psutil.Process(self._shell.pid)
            gone = _kill_procs([shell], kill=kill)
            if not gone:
                log.error('Failed to kill shell')
                return False
        self._wait_shell()
        log.warning('Shell closed')
        return True

    def _respawn_shell(self, kill: bool = False) -> bool:
        """Respawn the shell."""
        gone = self._close_shell(kill=kill)
        if not gone:
            log.error('Failed to close shell')
            return False
        self._open_shell()
        return True

    def _get_shell_children(self) -> list[psutil.Process]:
        """Get the shell children."""
        parent = psutil.Process(self._shell.pid)
        return parent.children(recursive=True)

    def _kill_shell_children(self, kill: bool = False) -> bool:
        """Kill the shell children."""
        children = self._get_shell_children()
        return _kill_procs(children, kill)

    def _ensure_shell(self) -> bool:
        """Ensure the shell is running."""
        if self._shell_gone():
            log.error('Shell has exited')
            self._wait_shell()
            self._open_shell()
            return False
        return True

    def _wait_done(self, fifo: Path) -> str:
        """Wait for the shell to finish."""
        fd = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
        try:
            if not self._ensure_shell():
                prompt = self._parse_prompt(self._get_prompt())
                return prompt.prompt

            log.debug(f'Waiting for shell to finish in {EXIT_TIMEOUT} seconds')
            ready, _, _ = select([fd], [], [], EXIT_TIMEOUT)

            if not ready:
                log.error('Shell did not finish in time')
                if not self._kill_shell_children():
                    log.error('Failed to terminate shell children')
                    _ = self._kill_shell_children(kill=True)
                ret = self._dummy_result('', -2, stderr='Command timed out')
                return ret.prompt.prompt
            return os.read(fd, 1024).decode('utf-8')
        finally:
            os.close(fd)

    def _get_prompt(self) -> str:
        with temp_fifo() as fifo:
            # Bash unsets PS1 on startup because it's not interactive
            ps1 = os.environ['PS1'].replace('"', '\\"')

            self._put_stdin(
                f'(R="$?"; PS1="{ps1}"; (exit "$R"); echo -n "${{PS1@P}}" >> {fifo}; exit "$R")'
            )
            ret = self._wait_done(fifo)
            log.debug(f'Got prompt: {ret}')
            return ret

    def _get_config(self) -> tuple[str | None, str | None, LlamaClientConfig | None]:
        """Get the system, goal, and config."""
        try:
            system = Path('/app/system.md').read_text('utf-8')
        except (FileNotFoundError, IsADirectoryError):
            log.debug('System prompt not found')
            system = None
        try:
            goal = Path('/app/goal').read_text('utf-8').strip()
        except (FileNotFoundError, IsADirectoryError):
            log.debug('Goal not found')
            goal = None
        try:
            config_json = Path('/app/config.json').read_text('utf-8')
            config = LlamaClientConfig.model_validate_json(config_json)
        except (FileNotFoundError, IsADirectoryError):
            log.debug('Config not found')
            config = None
        except ValidationError as e:
            log.debug(f'Invalid config: {e}')
            config = None
        return system, goal, config

    def _get_base(self) -> BaseResult:
        """Get the base result."""
        system, goal, config = self._get_config()
        return BaseResult(system=system, goal=goal, config=config)

    def _execute_shell(self, command: ShellCommand) -> ShellResult:
        invalid = self._lex(command.command)
        if invalid:
            log.error(f'Command refused due to syntax error: {command.command} ({invalid.stderr})')
            return invalid
        log.debug(f'Running command: {colored(command.command, COLORS.prompt)}')
        _ = self._ensure_shell()
        if self._streams_gone():
            _err = 'Shell streams are not available'
            raise ValueError(_err)

        if self._get_shell_children():
            # Can happen if the model starts background processes
            # TODO: Allow background processes?
            log.error('Shell still has old children')
            if not self._kill_shell_children():
                log.error('Failed to terminate old shell children')
                _ = self._kill_shell_children(kill=True)

        self._put_stdin(command.command)
        start = time.time()
        prompt = self._parse_prompt(self._get_prompt())
        delta = time.time() - start
        log.debug(f'Command exited with code {prompt.exit_code} in {delta:.2f}s')
        stdout = self._get_stdout()
        stderr = self._get_stderr()
        ret = ShellResult(
            command=command,
            stdout=stdout,
            stderr=stderr,
            exit_code=prompt.exit_code,
            prompt=prompt,
            **self._get_base().model_dump(),
        )
        log_output(log.debug, ret)
        return ret

    @overload
    def _execute_file(self, command: FileReadCommand) -> FileReadResult: ...

    @overload
    def _execute_file(self, command: FileWriteCommand) -> FileWriteResult: ...

    def _execute_file(self, command: AnyFileCommand) -> AnyFileResult:
        log.debug(f'Reading file: {colored(command.file, COLORS.prompt)}')
        errors: dict[type, str] = {
            FileNotFoundError: 'File not found',
            IsADirectoryError: 'Is a directory',
        }
        params = {'command': command, 'file': command.file, **self._get_base().model_dump()}
        try:
            if isinstance(command, FileReadCommand):
                content = Path(command.file).read_text('utf-8')
                return FileReadResult(content=content, **params)
            if isinstance(command, FileWriteCommand):
                _ = Path(command.file).write_text(command.content, 'utf-8')
                return FileWriteResult(written=len(command.content), **params)
        except Exception as e:
            _err = str(e)
            if type(e) in errors:
                _err = errors[type(e)]
            log.debug(f'Failed to read {command.file}: {_err}')
            cls = FileReadResult if isinstance(command, FileReadCommand) else FileWriteResult
            return cls(error=_err, **params)

    @overload
    def execute(self, command: ShellCommand) -> ShellResult: ...

    @overload
    def execute(self, command: FileReadCommand) -> FileReadResult: ...

    @overload
    def execute(self, command: FileWriteCommand) -> FileWriteResult: ...

    def execute(self, command: AnyCommand) -> AnyResult:
        """Execute a command."""
        if isinstance(command, ShellCommand):
            return self._execute_shell(command)
        if isinstance(command, FileReadCommand | FileWriteCommand):
            return self._execute_file(command)
        _err = f'Invalid command type: {type(command)}'
        raise ValueError(_err)
