"""Chat with the Llama using a history of commands."""

import itertools
import json
import os
from pathlib import Path
from typing import overload

from coloredlogs import logging
from llama_cpp import ChatCompletionRequestMessage, ChatCompletionRequestSystemMessage
from pydantic import BaseModel

from client.common import expect
from client.typedefs import (
    AnyCommands,
    AnyResult,
    FileReadResult,
    FileWriteResult,
    LlamaClientConfig,
    ShellResult,
)
from server.const import LLAMA_TOKEN_BUFFER
from server.llama_server import LlamaServer
from server.typedefs import (
    ResultHistory,
    SimpleAnyResult,
    SimpleFileReadResult,
    SimpleFileWriteResult,
    SimpleShellResult,
)

log = logging.getLogger(__name__)


@overload
def _simplify(result: ShellResult) -> SimpleShellResult: ...


@overload
def _simplify(result: FileReadResult) -> SimpleFileReadResult: ...


@overload
def _simplify(result: FileWriteResult) -> SimpleFileWriteResult: ...


def _simplify(result: AnyResult) -> SimpleAnyResult:
    if isinstance(result, ShellResult):
        return SimpleShellResult(
            command=result.command.command,
            prompt=result.prompt.prompt,
            stdout=''.join([v[1] for v in result.stdout]),
            stderr=''.join([v[1] for v in result.stderr]),
            exit_code=result.exit_code,
        )
    if isinstance(result, FileReadResult):
        return SimpleFileReadResult(
            file=result.file,
            content=result.content,
            error=result.error,
        )
    if isinstance(result, FileWriteResult):
        return SimpleFileWriteResult(
            file=result.file,
            content=result.command.content,
            written=result.written,
            error=result.error,
        )
    _err = f'Invalid result type: {type(result)}'
    raise ValueError(_err)


def _from_result(result: AnyResult) -> list[ChatCompletionRequestMessage]:
    return [
        {
            'role': 'assistant',
            'content': result.command.model_dump_json(),
        },
        {
            'role': 'user',
            'content': json.dumps(
                {k: v for k, v in _simplify(result).model_dump().items() if v},
                indent=2,
            ),
        },
    ]


def _from_commands(results: ResultHistory) -> list[ChatCompletionRequestMessage]:
    return list(itertools.chain.from_iterable([_from_result(result) for result in results]))


class LlamaChat(BaseModel):
    """Chat with the Llama using a history of commands."""

    _llama: LlamaServer
    _history: ResultHistory
    _config: LlamaClientConfig
    _system: str
    _goal: str
    _system_mutable: str

    def __init__(self, llama: LlamaServer) -> None:
        """Initialize the Llama chat."""
        super().__init__()
        self._llama = llama

        self._history = []
        self._config = LlamaClientConfig()
        self._system = Path('system.md').read_text(encoding='utf-8')
        self._goal = os.environ['LLAMA_DEFAULT_GOAL']

    def append_command(self, result: AnyResult) -> None:
        """Add a command to the chat history."""
        log.debug(f'Appending command: {result}')
        self._config = result.config or LlamaClientConfig()
        self._system_mutable = result.system or 'Write your system prompt to /app/system.md.'
        self._goal = result.goal or os.environ['LLAMA_DEFAULT_GOAL']
        self._history.append(result)

    def append_commands(self, results: list[AnyResult]) -> None:
        """Add multiple commands to the chat history."""
        for result in results:
            self.append_command(result)

    @property
    def system(self) -> ChatCompletionRequestSystemMessage:
        """Get the system prompt."""
        system: ChatCompletionRequestSystemMessage = {
            'role': 'system',
            'content': (
                f'# Primary goal: {self._goal}\n\n'
                f'{self._system}\n\n'
                f'=====\n\n'
                f'{self._system_mutable}'
            ),
        }
        return system

    def _get_prompt(self) -> list[ChatCompletionRequestMessage]:
        """Get the prompt to chat with the Llama, removing as many tokens as necessary."""
        system = self.system
        n_ctx = self._llama.server_config.n_ctx
        removed = 0
        tokens, initial_tokens = None, None
        while self._history:
            prompt = [system, *_from_commands(self._history)]
            tokens = len(self._llama.tokenize(prompt, special=True))
            if not initial_tokens:
                initial_tokens = tokens
            if tokens <= n_ctx - LLAMA_TOKEN_BUFFER:
                removed_tokens = initial_tokens - tokens
                log.debug(f'Removed {removed} commands ({removed_tokens} tokens)')
                return prompt
            removed += 1
            log.debug(f'Removed from history: {self._history.pop(0).command}')
        _err = f'No commands fit in {n_ctx} tokens (initial: {initial_tokens}, now {tokens})'
        # Happens if the context is small and it runs a command with huge output
        # Not sure how to handle this
        raise ValueError(_err)

    def get_commands(self) -> AnyCommands:
        """Retrieve the commands from the Llama."""
        prompt = self._get_prompt()
        response = self._llama.chat(prompt, self._config)
        ret = expect(response, AnyCommands, log_method=log.debug)
        log.debug(f'Received {len(ret.root)} commands')
        return ret
