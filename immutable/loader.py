"""Application loader."""

import importlib.abc
import importlib.machinery
import json
import logging
import os
import sys
from collections.abc import Sequence

import coloredlogs

coloredlogs.install(
    level=os.getenv('LOG_LEVEL', 'INFO').upper(),
    fmt='%(asctime) - %(levelname)-8s - %(name)-8s - %(message)s',
    datefmt='%M:%S.%f',
    isatty=True,
)
log = logging.getLogger(__name__)

MODULES = json.loads(os.environ['POCKET_ASI_MODULES'])


class FDLoader(importlib.abc.SourceLoader):
    """Loader for file descriptors."""

    fd: int

    def __init__(self, fd: int):
        """Initialize the loader with a file descriptor."""
        self.fd = fd

    def get_data(self, path: str) -> bytes:
        """Read the content of the file descriptor."""
        _ = path
        _ = os.lseek(self.fd, 0, os.SEEK_SET)
        content = b''
        while True:
            chunk = os.read(self.fd, 4096)
            if not chunk:
                break
            content += chunk
        return content

    def get_filename(self, fullname: str) -> str:
        """Return the filename of the file descriptor."""
        _ = fullname
        return f'fd:/{self.fd}'


class FDFinder(importlib.abc.MetaPathFinder):
    """Finder for file descriptors."""

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target=None,
    ) -> importlib.machinery.ModuleSpec | None:
        """Find the FD for a module."""
        _ = path, target
        if fullname in MODULES:
            fd = MODULES[fullname]
            return importlib.machinery.ModuleSpec(fullname, FDLoader(fd), origin=f'fd:/{fd}')
        return None


sys.meta_path.insert(0, FDFinder())

from immutable.app import run  # noqa: E402

run()
