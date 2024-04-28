"""Common utility functions."""

import json
import logging
import os
import random
import string
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import TypeVar

import coloredlogs
import termcolor
from pydantic import ValidationError
from termcolor._types import Color

from client.const import COLORS
from client.typedefs import (
    AnyCommand,
    AnyResult,
    FileReadCommand,
    FileReadResult,
    FileWriteCommand,
    FileWriteResult,
    ShellCommand,
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
            method(colored(result.content, COLORS.stdout))
        else:
            method(colored(result.error, COLORS.stderr))

    elif isinstance(result, FileWriteResult):
        if not result.error:
            method(colored(f'Wrote {result.written}B to {result.file}', COLORS.stdout))
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


DeterminationT = TypeVar('DeterminationT', bound=AnyCommand | AnyResult)


def _determine(
    what: str | dict,
    valid: list[type[DeterminationT]],
    log_method: Callable[[str], None],
) -> DeterminationT:
    """Determine the type of object."""
    ret = None
    for v in valid:
        with suppress(ValidationError):
            ret = v.parse_obj(what) if isinstance(what, dict) else v.model_validate_json(what)
            log_method(f'{what} is a {v.__name__}: {ret}')
    if ret:
        return ret
    _err = f'Invalid object: {what}'
    raise ValueError(_err)


def determine_command(command: str | dict, log_method: Callable[[str], None]) -> AnyCommand:
    """Determine the type of command."""
    _valid = [ShellCommand, FileReadCommand, FileWriteCommand]
    return _determine(command, _valid, log_method)


def determine_result(result: str | dict, log_method: Callable[[str], None]) -> AnyResult:
    """Determine the type of result."""
    _valid = [ShellResult, FileReadResult, FileWriteResult]
    return _determine(result, _valid, log_method)
