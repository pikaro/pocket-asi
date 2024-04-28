"""Type definitions for the server."""

from typing import TypeVar

from pydantic import BaseModel

from client.typedefs import AnyCommand, AnyResult, LlamaClientConfig


class LlamaServerConfig(BaseModel):
    """Options for llama.cpp server."""

    n_ctx: int
    max_tokens: int


ConfigT = TypeVar('ConfigT', LlamaServerConfig, LlamaClientConfig)


class SimpleShellResult(BaseModel):
    """Result of a command execution as expected by the LLM."""

    prompt: str
    command: str
    stdout: str | None = None
    stderr: str | None = None
    exit_code: int | None = None


class SimpleFileReadResult(BaseModel):
    """Result of a file read operation as expected by the LLM."""

    file: str
    content: str | None = None
    error: str | None = None


class SimpleFileWriteResult(BaseModel):
    """Result of a file write operation as expected by the LLM."""

    file: str
    content: str
    written: int | None = None
    error: str | None = None


SimpleAnyResult = SimpleShellResult | SimpleFileReadResult | SimpleFileWriteResult
ResultHistory = list[AnyResult]


LlmCommands = list[AnyCommand]
