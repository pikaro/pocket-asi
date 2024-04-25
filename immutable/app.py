"""Main entrypoint for the application."""

import json
from time import sleep

import pygments.formatters
import pygments.lexers
from coloredlogs import logging
from termcolor import colored

from immutable.llama import Llama
from immutable.shell import Shell
from immutable.typedefs import CommandResult

log = logging.getLogger(__name__)


def _highlight_bash(command: str) -> str:
    """Highlight a bash command."""
    lexer = pygments.lexers.BashLexer()
    formatter = pygments.formatters.TerminalFormatter()
    # Remove the trailing newline
    return pygments.highlight(command, lexer, formatter)[:-1]


def _log_output(result: CommandResult) -> None:
    """Log the output of a command."""
    lines = [(*v, log.info) for v in result['stdout']] + [(*v, log.error) for v in result['stderr']]
    for line in sorted(lines, key=lambda x: x[0]):
        line[2](line[1].rstrip('\n'))
    if result['exit_code']:
        log.error(f'Exited with code {result["exit_code"]}')


def run() -> None:
    """Run the application."""
    log.info('Starting application')
    shell = Shell()
    llama = Llama(shell)
    log.info('Starting shell')
    prompt = shell.run('true')['prompt']['prompt']
    log.info(f'Awaiting first command (PS1: {prompt})')
    while True:
        response = llama.prompt()
        command = response['message']['content']
        log.info(f'{colored(prompt, 'white', force_color=True)}{_highlight_bash(command)}')

        result = shell.run(command)
        prompt = result['prompt']['prompt']
        _log_output(result)
        llama.append(result)

        sleep(1)
        try:
            import mutable.app
        except ImportError:
            _err = 'Error importing app'
            log.exception(_err)
            continue

        try:
            run_result = mutable.app.run()
        except Exception as exc:
            _err = f'Error running app: {exc}'
            log.exception(_err)
            continue
        if run_result:
            log.info(json.dumps(run_result, indent=2))
