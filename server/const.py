"""Constants for the server."""

from client.typedefs import AnyCommand, FileReadCommand, FileWriteCommand, ShellCommand

LLAMA_SERVER_DEFAULTS = {
    'n_ctx': 8192,
    'max_tokens': 1024,
}

LLAMA_CLIENT_DEFAULTS = {
    'temperature': 1.0,
}

INITIAL_COMMANDS: list[AnyCommand] = [
    ShellCommand(command='ls -la', comment='List files in the current directory'),
    ShellCommand(command='git init', comment='Initialize a git repository'),
    FileWriteCommand(file='test.txt', content='Hello, world!'),
    FileReadCommand(file='test.txt'),
    ShellCommand(command='git status', comment='Check the status of the git repository'),
    ShellCommand(command='git add test.txt', comment='Add all files to the git repository'),
]

LLAMA_TOKEN_BUFFER = 512
