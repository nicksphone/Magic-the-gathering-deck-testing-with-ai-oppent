from __future__ import annotations


def known_unsupported_mechanics(oracle_text: str) -> list[str]:
    """Known gaps only; an empty result is not rules certification."""
    return ["bands with other"] if "bands with other" in (oracle_text or "").lower() else []
