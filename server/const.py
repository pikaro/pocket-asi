"""Constants for the server."""

LLAMA_SERVER_DEFAULTS = {
    'n_ctx': 8192,
    'max_tokens': 1024,
}

LLAMA_CLIENT_DEFAULTS = {
    'temperature': 1.0,
}

INITIAL_COMMANDS = [
    'ls -la',
    'cat app.py',
    'echo "Hello, world!" > hello.txt',
    'cat hello.txt',
    'cat system.md',
]

LLAMA_TOKEN_BUFFER = 512
