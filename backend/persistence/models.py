from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class CardCache(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    scryfall_id: str = Field(index=True, unique=True)
    name: str = Field(index=True)
    oracle_text: str = ""
    mana_cost: str = ""
    type_line: str = ""
    colors: str = ""
    power: Optional[str] = None
    toughness: Optional[str] = None
    image_uri: Optional[str] = None
    legalities_json: str = "{}"
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DeckRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    source: str = "user"
    mainboard_json: str
    sideboard_json: str = "[]"
    archetype_guess: str = "unknown"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MatchRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    deck_a_id: int
    deck_b_id: int
    winner: str
    mode: str
    turns: int
    log_json: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StatsSnapshot(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    label: str = Field(index=True)
    stats_json: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
