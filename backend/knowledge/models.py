from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class CardKnowledge(SQLModel, table=True):
    """Typed per-card knowledge consumed by the AI agent.

    ``oracle_source`` is provenance only: ``"scryfall"`` or ``"manual"``.
    Hand-written fallbacks never produce a knowledge row — they are deleted
    in Task 1.3 and their offline replacement lives in the committed seed.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    scryfall_id: str = Field(index=True, default="")
    oracle_source: str = "manual"
    play_value: Optional[float] = None
    threat_level: Optional[int] = None
    answerable_by_json: str = "[]"
    cast_windows_json: str = "[]"
    etb_impact: Optional[float] = None
    profiles_json: str = "{}"
    updated_at: datetime = Field(default_factory=datetime.utcnow)
