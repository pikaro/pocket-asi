"""Common type definitions."""

from typing import Literal

from pydantic import BaseModel
from termcolor._types import Color


class Prompt(BaseModel):
    """Components of the PS1 prompt."""

    prompt: str
    exit_code: int
    user: str
    host: str
    cwd: str
    usertype: Literal['root', 'user']


OutputLine = tuple[float, str]


class LlamaClientConfig(BaseModel):
    """Generation options for llama.cpp."""

    temperature: float | None = None


class BaseCommand(BaseModel):
    """Base command for all commands."""

    comment: str | None = None


class ShellCommand(BaseCommand):
    """A shell command to execute."""

    command: str


class FileReadCommand(BaseCommand):
    """A file read command."""

    file: str


class FileWriteCommand(BaseCommand):
    """A file write command."""

    file: str
    content: str


AnyCommand = ShellCommand | FileReadCommand | FileWriteCommand


class BaseResult(BaseModel):
    """Base result for all commands."""

    config: LlamaClientConfig | None
    system: str | None
    goal: str | None


class ShellResult(BaseResult):
    """Result of a command execution."""

    command: ShellCommand
    prompt: Prompt
    stdout: list[OutputLine]
    stderr: list[OutputLine]
    exit_code: int


class FileWriteResult(BaseResult):
    """Result of a file write operation."""

    command: FileWriteCommand
    file: str
    error: str | None = None
    written: int | None = None


class FileReadResult(BaseResult):
    """Result of a file read operation."""

    command: FileReadCommand
    file: str
    content: str | None = None
    error: str | None = None


AnyResult = ShellResult | FileReadResult | FileWriteResult


class TerminalColors(BaseModel):
    """Colors for the terminal output."""

    prompt: Color
    stdout: Color
    stderr: Color
    comment: Color
    stream: Color
    command: Color
