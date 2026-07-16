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
    card_faces_json: str = "[]"
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


class ActiveMatchRecord(SQLModel, table=True):
    """Durable application snapshot for an in-progress match."""

    id: str = Field(primary_key=True)
    state_json: str
    controller_json: str
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SimulationJobRecord(SQLModel, table=True):
    """Durable status/result row for an asynchronous simulator job."""

    id: str = Field(primary_key=True)
    status: str = "queued"
    completed_matches: int = 0
    total_matches: int = 0
    started_at: float = 0.0
    finished_at: Optional[float] = None
    error: Optional[str] = None
    result_json: Optional[str] = None
    request_json: str = "{}"


class StatsSnapshot(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    label: str = Field(index=True)
    stats_json: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TournamentEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    external_id: str = Field(index=True)
    source: str = Field(index=True)
    name: str = Field(index=True)
    format: str = "unknown"
    event_date: str = ""
    url: str = ""
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TournamentDeck(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: int = Field(index=True)
    player_name: str = Field(index=True)
    archetype: str = Field(index=True, default="unknown")
    placement: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    mainboard_json: str
    sideboard_json: str = "[]"
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=datetime.utcnow)
