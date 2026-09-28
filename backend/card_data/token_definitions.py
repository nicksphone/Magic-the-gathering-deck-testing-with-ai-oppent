from __future__ import annotations

import json
from pathlib import Path


_TOKENS = json.loads(Path(__file__).with_name("builtin_token_seed.json").read_text(encoding="utf-8"))


def named_artifact_token(name: str) -> dict | None:
    return next((dict(token) for key, token in _TOKENS.items() if key.casefold() == name.casefold()), None)
