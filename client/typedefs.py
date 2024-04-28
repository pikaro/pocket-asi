"""Common type definitions."""

from typing import Literal

from pydantic import BaseModel, RootModel
from pydantic_settings import BaseSettings, SettingsConfigDict
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


class LlamaClientConfig(BaseSettings):
    """Generation options for llama.cpp."""

    model_config = SettingsConfigDict(env_prefix='LLAMA_')

    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    min_p: float | None = None
    typical_p: float | None = None
    stream: bool | None = None
    seed: int | None = None
    max_tokens: int | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    repeat_penalty: float | None = None
    tfs_z: float | None = None
    mirostat_mode: int | None = None
    mirostat_tau: float | None = None
    mirostat_eta: float | None = None
    model: str | None = None
    logprobs: bool | None = None
    top_logprobs: int | None = None


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


AnyFileCommand = FileReadCommand | FileWriteCommand
AnyCommand = ShellCommand | FileReadCommand | FileWriteCommand


class AnyCommands(RootModel):
    """A list of commands."""

    root: list[AnyCommand]


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


AnyFileResult = FileReadResult | FileWriteResult
AnyResult = ShellResult | FileReadResult | FileWriteResult


class TerminalColors(BaseModel):
    """Colors for the terminal output."""

    prompt: Color
    stdout: Color
    stderr: Color
    comment: Color
    stream: Color
    command: Color
