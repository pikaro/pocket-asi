"""A simple script to write a file using the Path class."""

from pathlib import Path


def run():
    """Write a file using the Path class."""
    _text = 'Can we write a file from Python?'
    f = Path('output.txt')
    f.unlink(missing_ok=True)
    _ = f.write_text(_text)


if __name__ == '__main__':
    run()
