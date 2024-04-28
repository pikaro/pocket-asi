"""Constants. Used by both the client and the server.

Easier to have common constants for both in the client module due to the way the
application is loaded.
"""

import os

from bashlex.errors import ParsingError
from bashlex.tokenizer import MatchedPairError

from client.typedefs import TerminalColors

SHELL_INTERACTIVE_COMMANDS = [
    'vim',
    'nano',
    'less',
    'more',
]

# CLEANUPS: list[tuple[str, str]] = [
#    (r'```(python)?(.*?)```', r'\2'),
#    (r'\(Note:.*?\)', ''),
# ]

USERTYPES = {
    '$': 'user',
    '#': 'root',
}

EXIT_TIMEOUT = float(os.getenv('LLAMA_EXIT_TIMEOUT', '10.0'))
KILL_TIMEOUT = 1.0

LEXER_ERRORS: dict[type, int] = {
    MatchedPairError: 2,
    ParsingError: 2,
}

GENERIC_ERRORS: dict[type, tuple[int, str]] = {
    # TODO: Make pull request to bashlex
    # Bug in bashlex - ParsingError.__init__() missing 2 required positional arguments
    # File "/usr/local/lib/python3.12/site-packages/bashlex/subst.py", line 284
    TypeError: (-2, 'Internal error'),
}

COLORS = TerminalColors(
    prompt='white',
    stdout='light_grey',
    stderr='red',
    comment='cyan',
    stream='green',
    command='yellow',
)
