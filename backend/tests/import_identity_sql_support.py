"""Finite test-worker SQL spelling, not a new production/storage authority."""
import os
from pathlib import Path
from urllib.parse import unquote, urlsplit


def sqlite_guard_value(root, value):
    if value == ':memory:':
        return value
    text = os.fsdecode(value)
    if text.startswith('file:'):
        uri = urlsplit(text)
        assert uri.scheme == 'file' and not uri.netloc and not uri.fragment
        path = Path(unquote(uri.path))
        assert text == path.as_uri() + '?mode=ro', 'Only canonical readonly file URI'
    else:
        path = Path(text)
    assert path.is_absolute() and path == path.resolve(), 'Canonical absolute SQL path required'
    assert path.is_relative_to(root), 'SQL outside owned worker root'
    return str(path)
