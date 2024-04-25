"""Llama chatbot."""

import itertools
import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import cast

import ollama
from coloredlogs import logging
from pydantic import BaseModel

from immutable.common import fd_path
from immutable.shell import Shell
from immutable.typedefs import CommandHistory, CommandResult, LlmResponse

MODEL = 'llama3:8b'
# MODEL = 'code-qwen-7b-gguf-q5_0:latest'      Seems to work OK, but uses lots of Markdown
# MODEL = 'deepseek-coder-7b-gguf-q5_0:latest' Completely useless, writes blog posts

N_CTX = 8192
CONFIG_PATH = '/app/mutable/config.json'
TOKENIZER = '/app/immutable/tokenizer.json'
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'localhost')
CONFIG_BASE: ollama.Options = {'num_ctx': N_CTX, 'num_predict': N_CTX}

log = logging.getLogger(__name__)


def _initial_commands(shell) -> CommandHistory:
    commands = [
        'ls -la',
        'cat app.py',
        'echo "Hello, world!" > hello.txt',
        'cat hello.txt',
        'cat system.md',
    ]

    ret: CommandHistory = [shell.run(v) for v in commands]
    return ret


def _from_commands(commands: CommandHistory) -> Sequence[ollama.Message]:
    return list(
        itertools.chain.from_iterable(
            [
                [
                    {
                        'role': 'assistant',
                        'content': command['command'],
                    },
                    {
                        'role': 'user',
                        'content': (
                            ''.join(
                                [
                                    v[1]
                                    for v in sorted(
                                        command['stdout'] + command['stderr'], key=lambda x: x[0]
                                    )
                                ]
                            )
                            + '\n'
                            + command['prompt']['prompt']
                        ),
                    },
                ]
                for command in commands
            ]
        )
    )


class Llama(BaseModel):
    """Llama chatbot."""

    _client: ollama.Client
    _shell: Shell
    _history: CommandHistory

    def __init__(self, shell: Shell):
        """Initialize the Llama chatbot."""
        super().__init__()

        log.info(f'Initializing Llama with host {OLLAMA_HOST}')

        self._client = ollama.Client(host=f'http://{OLLAMA_HOST}:11434')
        self._shell = shell

        log.info('Executing initial commands')
        self._history = _initial_commands(shell)

        log.info('Llama initialized')

    @property
    def _config(self) -> ollama.Options:
        """Get the Llama configuration."""
        try:
            config_json = Path(CONFIG_PATH).read_text(encoding='utf-8')
        except FileNotFoundError:
            config_json = '{}'
        try:
            config: ollama.Options = json.loads(config_json)['LlmOptions']
        except (json.JSONDecodeError, KeyError):
            config: ollama.Options = {}

        ret: ollama.Options = config | CONFIG_BASE
        return ret

    def prompt(self) -> LlmResponse:
        """Prompt the LLM for shell input using the command / output history."""
        system_immutable = fd_path('system.md').read_text(encoding='utf-8')
        try:
            system_mutable = Path('system.md').read_text(encoding='utf-8')
        except FileNotFoundError:
            system_mutable = ''
        system = system_immutable + '\n\n=====\n\n' + system_mutable
        messages: Sequence[ollama.Message] = [
            {
                'role': 'system',
                'content': system,
            },
            *_from_commands(self._history),
        ]
        log.debug(f'Prompting LLM with {len(messages)} messages')
        return cast(
            LlmResponse,
            self._client.chat(
                model=MODEL,
                messages=messages,
                options=self._config,
            ),
        )

    def append(self, result: CommandResult) -> None:
        """Append a command result to the history."""
        self._history.append(result)
