from __future__ import annotations

from pydantic import BaseModel, Field


class BatchSimulationRequest(BaseModel):
    deck_a: list[dict]
    deck_b: list[dict]
    matches: int = Field(default=100, ge=1, le=500)
    difficulty: str = "master"
    max_ticks: int = Field(default=3000, ge=200, le=20000)
