from __future__ import annotations

import json
from datetime import datetime
from typing import Literal, Optional

from pydantic import field_validator
from sqlalchemy import String
from sqlmodel import Field, SQLModel


class CardKnowledge(SQLModel, table=True):
    """Canonical card knowledge and optional future AI tactical profiles.

    ``oracle_source`` is provenance only: ``"scryfall"`` or ``"manual"``.
    Bulk imports preserve the full canonical payload in ``profiles_json``.
    Rulings verification and tactical estimates are separate from ingestion;
    neither provenance nor an estimate alone certifies gameplay support.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    scryfall_id: str = Field(index=True, default="")
    oracle_source: Literal["scryfall", "manual"] = Field(default="manual", sa_type=String)
    play_value: Optional[float] = Field(default=None, ge=0, le=10)
    threat_level: Optional[int] = Field(default=None, ge=0, le=3)
    answerable_by_json: str = "[]"
    cast_windows_json: str = "[]"
    etb_impact: Optional[float] = None
    profiles_json: str = "{}"
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("answerable_by_json", "cast_windows_json")
    @classmethod
    def validate_string_list_json(cls, value: str) -> str:
        decoded = json.loads(value)
        if not isinstance(decoded, list) or any(not isinstance(item, str) for item in decoded):
            raise ValueError("Expected a JSON list of strings")
        return value

    @field_validator("profiles_json")
    @classmethod
    def validate_profiles_json(cls, value: str) -> str:
        json.loads(value)
        return value
