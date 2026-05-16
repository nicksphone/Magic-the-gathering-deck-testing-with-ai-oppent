from __future__ import annotations

import json
from typing import Any, Iterable

from sqlmodel import Session, func, select

from persistence.models import CardCache, DeckRecord, MatchRecord, StatsSnapshot, TournamentDeck, TournamentEvent


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

    def get_cached_card_by_name(self, name: str) -> CardCache | None:
        normalized = name.strip().lower()
        if not normalized:
            return None
        query = select(CardCache).where(func.lower(CardCache.name) == normalized)
        return self.session.exec(query).first()

    def get_cached_cards_by_names(self, names: list[str]) -> dict[str, CardCache]:
        if not names:
            return {}
        lowered = {n.strip().lower() for n in names if n.strip()}
        if not lowered:
            return {}
        rows = self.session.exec(select(CardCache).where(func.lower(CardCache.name).in_(lowered))).all()
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

    def upsert_tournament_event(
        self,
        *,
        external_id: str,
        source: str,
        name: str,
        format: str,
        event_date: str,
        url: str,
        metadata: dict[str, Any] | None = None,
    ) -> TournamentEvent:
        query = select(TournamentEvent).where(
            func.lower(TournamentEvent.external_id) == external_id.strip().lower(),
            func.lower(TournamentEvent.source) == source.strip().lower(),
        )
        row = self.session.exec(query).first()
        if row is None:
            row = TournamentEvent(
                external_id=external_id.strip(),
                source=source.strip(),
                name=name.strip(),
                format=format.strip(),
                event_date=event_date.strip(),
                url=url.strip(),
                metadata_json=json.dumps(metadata or {}),
            )
        else:
            row.name = name.strip()
            row.format = format.strip()
            row.event_date = event_date.strip()
            row.url = url.strip()
            row.metadata_json = json.dumps(metadata or {})
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def replace_tournament_event_decks(
        self,
        *,
        event_id: int,
        decks: list[dict[str, Any]],
    ) -> int:
        old_rows = self.session.exec(select(TournamentDeck).where(TournamentDeck.event_id == event_id)).all()
        for row in old_rows:
            self.session.delete(row)
        self.session.commit()

        created = 0
        for d in decks:
            row = TournamentDeck(
                event_id=event_id,
                player_name=str(d.get("player_name", "")).strip(),
                archetype=str(d.get("archetype", "unknown")).strip() or "unknown",
                placement=int(d.get("placement", 0) or 0),
                wins=int(d.get("wins", 0) or 0),
                losses=int(d.get("losses", 0) or 0),
                draws=int(d.get("draws", 0) or 0),
                mainboard_json=json.dumps(d.get("mainboard", [])),
                sideboard_json=json.dumps(d.get("sideboard", [])),
                metadata_json=json.dumps(d.get("metadata", {})),
            )
            self.session.add(row)
            created += 1
        self.session.commit()
        return created

    def list_tournament_events(self, limit: int = 100) -> list[TournamentEvent]:
        q = select(TournamentEvent).order_by(TournamentEvent.created_at.desc()).limit(max(1, int(limit)))
        return list(self.session.exec(q).all())

    def list_tournament_decks(self, event_id: int) -> list[TournamentDeck]:
        q = select(TournamentDeck).where(TournamentDeck.event_id == event_id).order_by(TournamentDeck.placement.asc())
        return list(self.session.exec(q).all())
