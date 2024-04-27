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


class CommandResult(BaseModel):
    """Result of a command execution."""

    command: str
    stdout: list[OutputLine]
    stderr: list[OutputLine]
    exit_code: int
    prompt: Prompt
    config: LlamaClientConfig | None
    system: str | None
    goal: str | None


class TerminalColors(BaseModel):
    """Colors for the terminal output."""

    prompt: Color
    stdout: Color
    stderr: Color
    comment: Color
    stream: Color
