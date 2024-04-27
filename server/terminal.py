"""Pretty output for the interaction."""

import logging
from typing import cast

import pygments
import pygments.formatters
import pygments.lexers
from pydantic import BaseModel

from client.common import colored, log_output
from client.const import COLORS
from client.typedefs import CommandResult
from server.common import env_bool

log = logging.getLogger(__name__)


def _highlight_bash(command: str | None) -> str:
    """Highlight a bash command."""
    if command is None:
        return ''
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
        log.info(f'Streaming: {self.stream}')

    @property
    def stream(self) -> bool:
        """Get the streaming status."""
        return self._stream

    def render_prompt(self, prompt: str | None = None, command: str | None = None) -> None:
        """Render a prompt."""
        prompt = colored(prompt, COLORS.prompt)
        command = _highlight_bash(command)
        if self.stream and not command:
            log.info(prompt)
        elif self.stream and not prompt:
            print(command)
        else:
            log.info(f'{prompt}{command}')

    def render(self, prompt: str | None, result: CommandResult, comment: str | None = None) -> None:
        """Render a command result."""
        # If not streaming and not other messages, assume previous prompt is still there
        if not self.stream:
            self.render_prompt(prompt=prompt, command=result.command)
        if comment:
            comment = colored(comment, COLORS.comment)
            log.info(comment)
        log_output(log.info, result)
        if self.stream:
            # Hacky, but works - should always be the coloredlogs handler, i.e. StreamHandler
            # Remove the newline only for this message so the command can be printed after
            # the prompt
            handler = cast(logging.StreamHandler, logging.getLogger().handlers[0])
            terminator = handler.terminator
            handler.terminator = ''
            self.render_prompt(prompt=result.prompt.prompt)
            handler.terminator = terminator
