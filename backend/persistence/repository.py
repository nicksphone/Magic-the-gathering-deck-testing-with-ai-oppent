from __future__ import annotations

import json
from typing import Any, Iterable

from sqlmodel import Session, select

from persistence.models import CardCache, DeckRecord, MatchRecord, StatsSnapshot


class Repository:
    def __init__(self, session: Session):
        self.session = session

    def upsert_card(self, payload: dict[str, Any]) -> CardCache:
        query = select(CardCache).where(CardCache.scryfall_id == payload["scryfall_id"])
        card = self.session.exec(query).first()
        if card is None:
            card = CardCache(**payload)
        else:
            for key, value in payload.items():
                setattr(card, key, value)
        self.session.add(card)
        self.session.commit()
        self.session.refresh(card)
        return card

    def list_cards(self) -> list[CardCache]:
        return list(self.session.exec(select(CardCache)).all())

    def get_cached_cards_by_names(self, names: list[str]) -> dict[str, CardCache]:
        if not names:
            return {}
        lowered = {n.lower() for n in names}
        rows = self.session.exec(select(CardCache)).all()
        out: dict[str, CardCache] = {}
        for row in rows:
            if row.name.lower() in lowered:
                out[row.name.lower()] = row
        return out

    def save_deck(self, name: str, source: str, mainboard: list[dict[str, Any]], sideboard: list[dict[str, Any]], archetype_guess: str) -> DeckRecord:
        record = DeckRecord(
            name=name,
            source=source,
            mainboard_json=json.dumps(mainboard),
            sideboard_json=json.dumps(sideboard),
            archetype_guess=archetype_guess,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def list_decks(self) -> list[DeckRecord]:
        return list(self.session.exec(select(DeckRecord).order_by(DeckRecord.created_at.desc())).all())

    def save_match(self, deck_a_id: int, deck_b_id: int, winner: str, mode: str, turns: int, log: Iterable[str]) -> MatchRecord:
        record = MatchRecord(
            deck_a_id=deck_a_id,
            deck_b_id=deck_b_id,
            winner=winner,
            mode=mode,
            turns=turns,
            log_json=json.dumps(list(log)),
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def list_matches(self) -> list[MatchRecord]:
        return list(self.session.exec(select(MatchRecord).order_by(MatchRecord.created_at.desc())).all())

    def save_snapshot(self, label: str, stats: dict[str, Any]) -> StatsSnapshot:
        record = StatsSnapshot(label=label, stats_json=json.dumps(stats))
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record
