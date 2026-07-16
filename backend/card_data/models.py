from __future__ import annotations

from pydantic import BaseModel


class CardFace(BaseModel):
    name: str
    mana_cost: str | None = None
    type_line: str | None = None
    oracle_text: str | None = None
    power: str | None = None
    toughness: str | None = None
    image_uri: str | None = None


class CardModel(BaseModel):
    scryfall_id: str
    name: str
    mana_cost: str = ""
    type_line: str = ""
    oracle_text: str = ""
    colors: list[str] = []
    power: str | None = None
    toughness: str | None = None
    keywords: list[str] = []
    legalities: dict[str, str] = {}
    rulings: list[dict] = []
    image_uri: str | None = None
    card_faces: list[CardFace] = []
