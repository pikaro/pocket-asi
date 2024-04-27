"""Pretty output for the interaction."""

import logging

import pygments
import pygments.formatters
import pygments.lexers
from pydantic import BaseModel

from client.common import colored, install_coloredlogs, log_output
from client.const import COLORS
from client.typedefs import CommandResult
from server.common import env_bool, get_streaming_logger

log = logging.getLogger(__name__)


def _highlight_bash(command: str) -> str:
    """Highlight a bash command."""
    lexer = pygments.lexers.BashLexer()
    formatter = pygments.formatters.TerminalFormatter()
    # Remove the trailing newline
    return pygments.highlight(command, lexer, formatter)[:-1]


class Terminal(BaseModel):
    """Pretty output for the interaction."""

    _stream: bool
    _streamer: logging.Logger

    def __init__(self):
        """Initialize the terminal."""
        super().__init__()
        self._stream = (
            not env_bool('LLAMA_STREAM_RESPONSE')
        ) and log.getEffectiveLevel() >= logging.INFO
        log.info(f'Streaming: {self._stream}')

    def render(self, prompt: str | None, result: CommandResult, comment: str | None = None) -> None:
        """Render a command result."""
        if not prompt:
            prompt = '<uninitialized> '
        prompt = colored(prompt, COLORS.prompt)
        command = _highlight_bash(result.command)
        result_prompt = colored(result.prompt.prompt, COLORS.prompt)
        comment = colored(comment, COLORS.comment)
        # If not streaming and not other messages, assume previous prompt is still there
        if self._stream:
            print(command)
            if comment:
                log.info(comment)
        else:
            log.info(f'{prompt}{command}')
        log_output(log, result)
        if self._stream:
            root_logger = logging.getLogger()
            terminator = root_logger.handlers[0].terminator
            root_logger.handlers[0].terminator = ''
            log.info(result_prompt)
            root_logger.handlers[0].terminator = terminator
