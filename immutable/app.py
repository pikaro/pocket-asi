"""Main entrypoint for the application."""

import json
from time import sleep

from coloredlogs import logging

from immutable.llama import Llama
from immutable.shell import Shell
from immutable.typedefs import CommandResult

log = logging.getLogger(__name__)


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
    ps1 = shell.run('true')['ps1']['ps1']
    log.info(f'Awaiting first command (PS1: {ps1})')
    while True:
        response = llama.prompt()
        command = response['message']['content']
        log.info(f'{ps1} {command}')

        result = shell.run(command)
        ps1 = result['ps1']['ps1']
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
