"""Constants for the server."""

from client.typedefs import (
    AnyCommand,
    FileReadCommand,
    FileWriteCommand,
    ShellCommand,
)

INITIAL_COMMANDS: list[AnyCommand] = [
    ShellCommand(command='ls -la', comment='List files in the current directory'),
    ShellCommand(command='git init', comment='Initialize a git repository'),
    FileWriteCommand(file='test.txt', content='Hello, world!'),
    FileReadCommand(file='test.txt'),
    ShellCommand(command='git status', comment='Check the status of the git repository'),
    ShellCommand(command='git add test.txt', comment='Add all files to the git repository'),
]

LLAMA_TOKEN_BUFFER = 512
