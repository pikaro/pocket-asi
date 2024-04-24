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

from immutable.shell import Shell
from immutable.typedefs import CommandHistory, CommandResult, LlmResponse

MODEL = 'llama3:8b'
N_CTX = 8192
CONFIG_PATH = '/app/mutable/config.json'
TOKENIZER = '/app/immutable/tokenizer.json'
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'localhost')

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
                            + command['ps1']['ps1']
                        ),
                    },
                ]
                for command in commands
            ]
        )
    )


class Llama(BaseModel):
    """Llama chatbot."""

    _config: ollama.Options
    _client: ollama.Client
    _shell: Shell
    _history: CommandHistory

    def __init__(self, shell: Shell):
        """Initialize the Llama chatbot."""
        super().__init__()

        self._client = ollama.Client(host=f'http://{OLLAMA_HOST}:11434')
        self._shell = shell

        try:
            config_json = Path(CONFIG_PATH).read_text(encoding='utf-8')
        except FileNotFoundError:
            config_json = '{}'

        try:
            config: ollama.Options = json.loads(config_json)
        except json.JSONDecodeError:
            config = {}

        self._config = config | {'num_ctx': N_CTX, 'num_predict': N_CTX}
        self._history = _initial_commands(shell)

    def prompt(self) -> LlmResponse:
        """Prompt the LLM for shell input using the command / output history."""
        system_immutable = Path('/app/immutable/system.md').read_text(encoding='utf-8')
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
