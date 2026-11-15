from __future__ import annotations

"""Per-card verified knowledge, separate from display metadata in CardCache."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from knowledge.models import CardKnowledge

__all__ = ["CardKnowledge"]


def __getattr__(name):
    if name != "CardKnowledge":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from knowledge.models import CardKnowledge
    globals()[name] = CardKnowledge
    return CardKnowledge


def __dir__():
    return sorted(set(globals()) | set(__all__))
