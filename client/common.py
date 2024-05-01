"""Common utility functions."""

import json
import logging
import os
import random
import string
from collections.abc import Callable
from contextlib import suppress
from inspect import isclass
from pathlib import Path
from socket import socket
from types import UnionType
from typing import TypeVar, get_args, get_origin, overload

import coloredlogs
import termcolor
from pydantic import BaseModel, ValidationError
from termcolor._types import Color

from client.const import COLORS
from client.typedefs import (
    AnyMessage,
    AnyResult,
    FileReadResult,
    FileWriteResult,
    ShellResult,
)


def random_string(length: int) -> str:
    """Generate a random string."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))  # noqa: S311


def fd_path(name: str) -> Path:
    """Get the file descriptor path for a file."""
    files = json.loads(os.environ['POCKET_ASI_FILES'])
    try:
        return Path(f'/proc/self/fd/{files[name]}')
    except KeyError as e:
        _err = f'File not found: {name}'
        raise FileNotFoundError(_err) from e


def colored(text: str | None, color: Color) -> str:
    """Color a string."""
    if not text:
        return ''
    return termcolor.colored(text, color, force_color=True)


def log_output(method, result: AnyResult) -> None:
    """Log the output of a command."""
    if isinstance(result, ShellResult):
        stdout = [(*v, COLORS.stdout) for v in result.stdout]
        stderr = [(*v, COLORS.stderr) for v in result.stderr]
        for line in sorted(stdout + stderr, key=lambda x: x[0]):
            method(colored(line[1].rstrip('\n'), line[-1]))
        if result.exit_code:
            method(colored(f'Exited with code {result.exit_code}', COLORS.stderr))

    elif isinstance(result, FileReadResult):
        if not result.error:
            content = result.content or ''
            method(colored(f'Read {len(content)}B from {result.file}', COLORS.stdout))
            for line in content.splitlines():
                method(colored(line, COLORS.stdout))
        else:
            method(colored(result.error, COLORS.stderr))

    elif isinstance(result, FileWriteResult):
        if not result.error:
            method(colored(f'Wrote {result.written}B to {result.file}', COLORS.stdout))
            for line in result.command.content.splitlines():
                method(colored(line, COLORS.stdout))
        else:
            method(colored(result.error, COLORS.stderr))

    else:
        _err = f'Invalid result type: {type(result)}'
        raise TypeError(_err)


def install_coloredlogs(log: logging.Logger | None = None) -> None:
    """Install colored logs to the root logger or a specific logger."""
    kwargs = {'logger': log} if log else {}
    coloredlogs.install(
        level=os.getenv('LOG_LEVEL', 'INFO').upper(),
        fmt='server-1  | %(asctime)-9s - %(levelname)-8s - %(name)-22s - %(message)s',
        datefmt='%M:%S.%f',
        isatty=True,
        **kwargs,
    )


DeterminationT = TypeVar('DeterminationT', bound=AnyMessage)


def _determine(
    what: str | dict, as_a: type[DeterminationT], log_method: Callable[[str], None]
) -> DeterminationT:
    ret = as_a.model_validate(what) if isinstance(what, dict) else as_a.model_validate_json(what)
    log_method(f'Determined {ret.__class__.__name__}: {ret}')
    return ret


@overload
def expect(
    what: str | dict, as_a: type[UnionType], log_method: Callable[[str], None]
) -> AnyMessage: ...
@overload
def expect(
    what: str | dict, as_a: type[DeterminationT], log_method: Callable[[str], None]
) -> DeterminationT: ...


def expect(what, as_a, log_method):
    """Determine the type of object."""
    if get_origin(as_a) == UnionType:
        for v in get_args(as_a):
            with suppress(ValidationError):
                return _determine(what, v, log_method)
        _err = f'No valid type found for {what} in {as_a}'
    elif isclass(as_a) and issubclass(as_a, AnyMessage):
        return _determine(what, as_a, log_method)
    _err = f'Invalid object: {what}'
    raise ValueError(_err)


def send_model(sock: socket | None, model: BaseModel) -> None:
    """Send a model to a socket."""
    if sock is None:
        _err = 'Connection closed'
        raise ConnectionError(_err)
    sock.sendall(model.model_dump_json().encode('utf-8') + b'\0')


def read_message(sock: socket | None) -> str:
    """Read a message from the connection."""
    buf = b''
    if sock is None:
        _err = 'Connection closed'
        raise ConnectionError(_err)
    while True:
        data = sock.recv(4096)
        if not data:
            _err = 'Connection closed'
            raise ConnectionError(_err)
        buf += data
        if b'\0' in buf:
            message, buf = buf.split(b'\0', 1)
            return message.decode('utf-8')
