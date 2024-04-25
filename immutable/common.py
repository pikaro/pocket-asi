"""Common utility functions."""

import json
import os
import random
import string
from pathlib import Path

POCKET_ASI_FILES = json.loads(os.environ['POCKET_ASI_FILES'])


def random_string(length: int) -> str:
    """Generate a random string."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))  # noqa: S311


def fd_path(name: str) -> Path:
    """Get the file descriptor path for a file."""
    try:
        return Path(f'/proc/self/fd/{POCKET_ASI_FILES[name]}')
    except KeyError as e:
        _err = f'File not found: {name}'
        raise FileNotFoundError(_err) from e
