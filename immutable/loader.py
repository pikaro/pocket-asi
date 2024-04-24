"""Application loader."""

import importlib.abc
import importlib.machinery
import json
import logging
import os
import sys
from collections.abc import Sequence
from pathlib import Path

import coloredlogs

coloredlogs.install(
    level=os.getenv('LOG_LEVEL', 'INFO').upper(),
    fmt='%(asctime)-9s - %(levelname)-8s - %(name)-8s - %(message)s',
    datefmt='%M:%S.%f',
    isatty=True,
)
log = logging.getLogger(__name__)

POCKET_ASI_MODULE = os.environ['POCKET_ASI_MODULE']
POCKET_ASI_FILES = json.loads(os.environ['POCKET_ASI_FILES'])
log.info(f'Received {len(POCKET_ASI_FILES)} files as FDs')


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

    def is_package(self, fullname):
        """Check if the module is a package."""
        return fullname.endswith('.__init__')


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

        if fullname == POCKET_ASI_MODULE:
            module_name = '__init__.py'
        elif fullname.startswith(POCKET_ASI_MODULE):
            module_name = f'{fullname.split('.')[-1]}.py'
        else:
            return None
        if module_name in POCKET_ASI_FILES:
            fd = POCKET_ASI_FILES[module_name]
            spec = importlib.machinery.ModuleSpec(fullname, FDLoader(fd), origin=f'fd:/{fd}')
            spec.submodule_search_locations = []
            if fullname.endswith('.__init__'):
                if not spec.origin:
                    _err = 'Cannot determine origin for package'
                    raise ImportError(_err)
                parent = Path(spec.origin).parent.as_posix()
                spec.submodule_search_locations = [parent]
            return spec
        return None


sys.meta_path.insert(0, FDFinder())

from immutable.app import run  # noqa: E402

log.info('Loaded application from file descriptors')

run()
