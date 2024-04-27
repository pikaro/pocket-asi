"""Common utility functions."""

import json
import logging
import os
import random
import string
from pathlib import Path

import coloredlogs
import termcolor
from termcolor._types import Color

from client.const import COLORS
from client.typedefs import CommandResult


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


def log_output(log: logging.Logger, result: CommandResult) -> None:
    """Log the output of a command."""
    stdout = [(*v, COLORS.stdout) for v in result.stdout]
    stderr = [(*v, COLORS.stderr) for v in result.stderr]
    for line in sorted(stdout + stderr, key=lambda x: x[0]):
        log.info(colored(line[1].rstrip('\n'), line[-1]))
    if result.exit_code:
        log.error(f'Exited with code {result.exit_code}')


def install_coloredlogs(log: logging.Logger | None = None) -> None:
    """Install colored logs to the root logger or a specific logger."""
    kwargs = {'logger': log} if log else {}
    coloredlogs.install(
        level=os.getenv('LOG_LEVEL', 'INFO').upper(),
        fmt='%(asctime)-9s - %(levelname)-8s - %(name)-22s - %(message)s',
        datefmt='%M:%S.%f',
        isatty=True,
        **kwargs,
    )
