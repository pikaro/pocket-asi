"""Constants for the server."""

from pathlib import Path

from client.typedefs import AnyCommand, FileReadCommand, FileWriteCommand, ShellCommand

LLAMA_SERVER_DEFAULTS = {
    'n_ctx': 8192,
    'max_tokens': 1024,
}

LLAMA_CLIENT_DEFAULTS = {
    'temperature': 1.0,
}

main_py = Path('mutable/main.py').read_text(encoding='utf-8')

INITIAL_COMMANDS: list[AnyCommand] = [
    ShellCommand(command='ls -la', comment='List files in the current directory'),
    FileWriteCommand(file='/app/app.py', content=main_py, comment='Write to a file'),
    ShellCommand(command='python3 /app/app.py', comment='Run the Python script'),
    FileReadCommand(file='/app/output.txt', comment='Read the output file'),
]

LLAMA_TOKEN_BUFFER = 512
