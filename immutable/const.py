"""Constants."""

SHELL_INTERACTIVE_COMMANDS = [
    'vim',
    'nano',
    'less',
    'more',
]

CLEANUPS: list[tuple[str, str]] = [
    (r'```(python)?(.*?)```', r'\2'),
    (r'\(Note:.*?\)', ''),
]
