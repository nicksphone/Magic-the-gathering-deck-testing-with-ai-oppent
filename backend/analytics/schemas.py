from __future__ import annotations

from pydantic import BaseModel, Field


class BatchSimulationRequest(BaseModel):
    deck_a: list[dict]
    deck_b: list[dict]
    matches: int = Field(default=100, ge=1, le=500)
    difficulty: str = "master"
    max_ticks: int = Field(default=6000, ge=500, le=50000)


class AIDiagnosticsRequest(BaseModel):
    deck_ids: list[int] = []
    include_builtins: bool = True
    max_decks: int = Field(default=10, ge=2, le=20)
    matches_per_pair: int = Field(default=5, ge=1, le=100)
    difficulty: str = "master"
    max_ticks: int = Field(default=6000, ge=500, le=50000)
