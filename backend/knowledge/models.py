from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class CardKnowledge(SQLModel, table=True):
    """Canonical card knowledge and optional future AI tactical profiles.

    ``oracle_source`` is provenance only: ``"scryfall"`` or ``"manual"``.
    Bulk imports preserve the full canonical payload in ``profiles_json``.
    Rulings verification and tactical estimates are separate from ingestion;
    the current AI does not yet consume these persisted profiles.
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
