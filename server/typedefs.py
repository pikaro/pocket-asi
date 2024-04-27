"""Type definitions for the server."""

from typing import TypeVar

from pydantic import BaseModel

from client.typedefs import CommandResult, LlamaClientConfig


class LlamaServerConfig(BaseModel):
    """Options for llama.cpp server."""

    n_ctx: int
    max_tokens: int


ConfigT = TypeVar('ConfigT', LlamaServerConfig, LlamaClientConfig)


class SimpleCommandResult(BaseModel):
    """Result of a command execution as expected by the LLM."""

    prompt: str
    stdout: str | None = None
    stderr: str | None = None
    exit_code: int | None = None


CommandHistory = list[CommandResult]


class LlmCommands(BaseModel):
    """Commands to be executed by the LLM server."""

    commands: list[str]
    comment: str | None = None
