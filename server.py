#!/usr/bin/env python3

"""Llama server."""

import logging

from dotenv import load_dotenv

from client.common import install_coloredlogs

_ = load_dotenv()


from server import run  # noqa: E402

log = logging.getLogger(__name__)
install_coloredlogs()

run()
