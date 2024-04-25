"""Common type definitions."""

from typing import Literal, TypedDict

import ollama


class Prompt(TypedDict):
    """Components of the PS1 prompt."""

    prompt: str
    exit_code: int
    user: str
    host: str
    cwd: str
    usertype: Literal['root', 'user']


OutputLine = tuple[float, str]


class CommandResult(TypedDict):
    """Result of a command execution."""

    command: str
    stdout: list[OutputLine]
    stderr: list[OutputLine]
    exit_code: int
    prompt: Prompt


CommandHistory = list[CommandResult]


class LlmResponse(TypedDict):
    """Response from the LLM server."""

    message: ollama.Message
    done: bool
    total_duration: int
    load_duration: int
    prompt_eval_duration: int
    prompt_eval_count: int
    eval_duration: int
    eval_count: int
