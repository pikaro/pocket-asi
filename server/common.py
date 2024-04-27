"""Common utilities for the server."""

import logging
import os
import sys


def env_bool(name: str, default: bool = False) -> bool:
    """Return a boolean value from the environment."""
    return os.getenv(name, str(default)).lower() in ('true', '1')


def get_streaming_logger(cls: object) -> logging.Logger:
    """Get a streaming logger."""
    stream = logging.getLogger(cls.__class__.__name__)
    stream.propagate = False
    stream.handlers.clear()
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.terminator = ''
    stream.setLevel(logging.INFO)
    stream_handler.setFormatter(logging.Formatter('%(message)s'))
    stream.addHandler(stream_handler)
    return stream
