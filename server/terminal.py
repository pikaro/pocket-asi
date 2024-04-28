"""Pretty output for the interaction."""

import logging
from typing import cast

import pygments
import pygments.formatters
import pygments.lexers
from pydantic import BaseModel

from client.common import colored, log_output
from client.const import COLORS
from client.typedefs import (
    AnyCommand,
    AnyResult,
    FileReadCommand,
    FileWriteCommand,
    ShellCommand,
    ShellResult,
)

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

    suspended: bool = False
    _stream: bool
    _streamer: logging.Logger
    _have_prompt: bool = False

    def __init__(self, stream: bool):
        """Initialize the terminal."""
        super().__init__()
        self._stream = stream
        log.info(f'Streaming: {self.stream}')

    @property
    def stream(self) -> bool:
        """Get the streaming status."""
        return self._stream

    def render_prompt(self, prompt: str | None = None, command: AnyCommand | None = None) -> None:
        """Render a prompt."""
        if self.suspended:
            return
        prompt = colored(prompt, COLORS.prompt)
        command_text = ''
        if isinstance(command, ShellCommand):
            command_text = _highlight_bash(command.command)
        elif isinstance(command, FileReadCommand):
            command_text = colored(f'read({command.file})', COLORS.command)
        elif isinstance(command, FileWriteCommand):
            count = len(command.content)
            command_text = colored(f'write({command.file}, {count} bytes)', COLORS.command)
        if self.stream and not command:
            log.info(prompt)
        elif self.stream and not prompt and self._have_prompt:
            print(command_text)
        else:
            log.info(f'{prompt}{command_text}')
        self._have_prompt = True

    def render(self, prompt: str | None, result: AnyResult, comment: str | None = None) -> None:
        """Render a command result."""
        if self.suspended:
            return
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
            if isinstance(result, ShellResult):
                prompt = result.prompt.prompt
            self.render_prompt(prompt=prompt)
            handler.terminator = terminator
