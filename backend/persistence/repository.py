from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterable

from sqlmodel import Session, func, select
from sqlalchemy import or_

from knowledge.models import CardKnowledge
from persistence.models import (
    ActiveMatchRecord,
    CardCache,
    DeckRecord,
    MatchRecord,
    MatchStartReceipt,
    SimulationJobRecord,
    StatsSnapshot,
    TournamentDeck,
    TournamentEvent,
)


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

    def upsert_card_knowledge(self, payload: dict[str, Any]) -> CardKnowledge:
        """Upsert one CardKnowledge row keyed by normalized card name."""
        normalized = str(payload["name"]).strip()
        query = select(CardKnowledge).where(
            func.lower(CardKnowledge.name) == normalized.lower()
        )
        row = self.session.exec(query).first()
        values = {
            "scryfall_id": str(payload.get("scryfall_id", "")),
            "oracle_source": str(payload.get("oracle_source", "manual")),
            "play_value": payload.get("play_value"),
            "threat_level": payload.get("threat_level"),
            "answerable_by_json": json.dumps(payload.get("answerable_by") or []),
            "cast_windows_json": json.dumps(payload.get("cast_windows") or []),
            "etb_impact": payload.get("etb_impact"),
            "profiles_json": json.dumps(payload.get("profiles") or {}),
            "updated_at": datetime.utcnow(),
        }
        if row is None:
            row = CardKnowledge(name=normalized, **values)
        else:
            for key, value in values.items():
                setattr(row, key, value)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def get_card_knowledge(self, name: str) -> CardKnowledge | None:
        return self.get_card_knowledge_by_names([name]).get(str(name or '').strip().casefold())

    def get_card_knowledge_by_names(self, names: list[str]) -> dict[str, CardKnowledge]:
        requested = {str(name).strip() for name in names if str(name or '').strip()}
        if not requested:
            return {}
        normalized = {name.casefold() for name in requested}
        rows = self.session.exec(select(CardKnowledge).where(CardKnowledge.name.in_(requested))).all()
        out = {row.name.casefold(): row for row in rows}
        missing = normalized - out.keys()
        if missing:
            rows = self.session.exec(select(CardKnowledge).where(func.lower(CardKnowledge.name).in_(missing))).all()
            out.update({row.name.casefold(): row for row in rows})
        missing = normalized - out.keys()
        if not missing:
            return out
        predicates = []
        for name in requested:
            if name.casefold() not in missing:
                continue
            predicates.extend([CardKnowledge.name.startswith(name + ' // ', autoescape=True),
                               CardKnowledge.name.endswith(' // ' + name, autoescape=True)])
        rows = self.session.exec(select(CardKnowledge).where(or_(*predicates)).order_by(CardKnowledge.id)).all()
        for row in rows:
            try:
                raw = json.loads(row.profiles_json).get('card_data') or {}
            except (TypeError, ValueError, AttributeError):
                raw = {}
            if not isinstance(raw, dict):
                raw = {}
            for alias in _name_aliases(row.name, str(raw.get('layout') or ''), str(raw.get('type_line') or '')):
                if alias.casefold() in normalized:
                    out.setdefault(alias.casefold(), row)
        return out

    def list_card_knowledge(self, names: list[str] | None = None) -> list[CardKnowledge]:
        query = select(CardKnowledge)
        if names:
            normalized = {str(n).strip().lower() for n in names if str(n).strip()}
            if normalized:
                query = query.where(func.lower(CardKnowledge.name).in_(normalized))
        return list(self.session.exec(query).all())

    def list_card_knowledge_names(self) -> list[str]:
        query = select(CardKnowledge.name).where(
            CardKnowledge.oracle_source == "scryfall",
            ~CardKnowledge.name.like("% [oracle:%]"),
        )
        return list(self.session.exec(query).all())

    def get_cached_card_by_name(self, name: str) -> CardCache | None:
        return self.get_cached_cards_by_names([name]).get(name.strip().lower())

    def get_cached_cards_by_names(self, names: list[str]) -> dict[str, CardCache]:
        if not names:
            return {}
        lowered = {n.strip().lower() for n in names if n.strip()}
        if not lowered:
            return {}
        # Exact Oracle names must win over face aliases regardless of row order.
        out: dict[str, CardCache] = {
            row.name.strip().lower(): row
            for row in self.session.exec(select(CardCache).where(or_(
                CardCache.name.in_({name.strip() for name in names}), func.lower(CardCache.name).in_(lowered)))).all()
        }
        if len(out) == len(lowered):
            return out
        missing = lowered - out.keys()
        predicates = []
        for name in missing:
            predicates.extend([func.lower(CardCache.name).startswith(name + ' // ', autoescape=True),
                               func.lower(CardCache.name).endswith(' // ' + name, autoescape=True)])
        rows = self.session.exec(select(CardCache).where(or_(*predicates)).order_by(CardCache.id)).all()
        for row in rows:
            for alias in _name_aliases(row.name, row.layout, row.type_line):
                if alias in lowered:
                    out.setdefault(alias, row)
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

    def save_catalog_deck(self, name: str, source: str, mainboard: list[dict[str, Any]], sideboard: list[dict[str, Any]], archetype_guess: str) -> DeckRecord:
        if not source.lower().startswith("expansion_top:"):
            raise ValueError("Catalog deck source must identify an expansion")
        record = self.session.exec(
            select(DeckRecord).where(DeckRecord.source == source).order_by(DeckRecord.created_at.desc(), DeckRecord.id.desc())
        ).first()
        if record is None:
            return self.save_deck(name, source, mainboard, sideboard, archetype_guess)
        record.name = name
        record.mainboard_json = json.dumps(mainboard)
        record.sideboard_json = json.dumps(sideboard)
        record.archetype_guess = archetype_guess
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def list_decks(self) -> list[DeckRecord]:
        return list(self.session.exec(select(DeckRecord).order_by(DeckRecord.created_at.desc(), DeckRecord.id.desc())).all())

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
        self._commit_match_write()
        self.session.refresh(record)
        return record

    def list_matches(self) -> list[MatchRecord]:
        return list(self.session.exec(select(MatchRecord).order_by(MatchRecord.created_at.desc())).all())

    def save_active_match(self, match_id: str, state_json: str, controller_json: str) -> ActiveMatchRecord:
        row = self.session.get(ActiveMatchRecord, match_id)
        if row is None:
            row = ActiveMatchRecord(id=match_id, state_json=state_json, controller_json=controller_json)
        else:
            row.state_json = state_json
            row.controller_json = controller_json
        self.session.add(row)
        self._commit_match_write()
        self.session.refresh(row)
        return row

    def _commit_match_write(self) -> None:
        if getattr(self, "_atomic_match_write", False):
            self.session.flush()
        else:
            self.session.commit()

    @contextmanager
    def atomic_match_writes(self):
        """Commit game history and its active snapshot as one storage unit."""
        self._atomic_match_write = True
        try:
            yield
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        finally:
            self._atomic_match_write = False

    def get_active_match(self, match_id: str) -> ActiveMatchRecord | None:
        return self.session.get(ActiveMatchRecord, match_id)

    def get_match_start_receipt(self, key: str) -> MatchStartReceipt | None:
        return self.session.get(MatchStartReceipt, key)

    def save_match_start_receipt(self, key: str, request_hash: str, match_id: str) -> None:
        self.session.add(MatchStartReceipt(key=key, request_hash=request_hash, match_id=match_id))
        self._commit_match_write()

    def list_active_matches(self) -> list[ActiveMatchRecord]:
        return list(self.session.exec(select(ActiveMatchRecord).order_by(ActiveMatchRecord.updated_at.desc())).all())

    def delete_active_match(self, match_id: str) -> None:
        row = self.session.get(ActiveMatchRecord, match_id)
        if row is not None:
            self.session.delete(row)
            self.session.commit()

    def save_simulation_job(self, payload: dict[str, Any]) -> SimulationJobRecord:
        row = self.session.get(SimulationJobRecord, str(payload["job_id"]))
        values = {
            "status": str(payload.get("status", "queued")),
            "completed_matches": int(payload.get("completed_matches", 0)),
            "total_matches": int(payload.get("total_matches", 0)),
            "started_at": float(payload.get("started_at", 0.0)),
            "finished_at": payload.get("finished_at"),
            "error": payload.get("error"),
            "result_json": json.dumps(payload.get("result")) if payload.get("result") is not None else None,
            "request_json": json.dumps(payload.get("request", {})),
        }
        if row is None:
            row = SimulationJobRecord(id=str(payload["job_id"]), **values)
        else:
            for key, value in values.items():
                setattr(row, key, value)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def get_simulation_job(self, job_id: str) -> SimulationJobRecord | None:
        return self.session.get(SimulationJobRecord, job_id)

    def count_simulation_jobs(self) -> int:
        return self.session.exec(select(func.count()).select_from(SimulationJobRecord)).one()

    def list_simulation_jobs(self, limit: int = 20) -> list[SimulationJobRecord]:
        return list(self.session.exec(select(SimulationJobRecord).order_by(SimulationJobRecord.started_at.desc()).limit(limit)).all())

    def list_unfinished_simulation_jobs(self) -> list[SimulationJobRecord]:
        return list(self.session.exec(select(SimulationJobRecord).where(SimulationJobRecord.status.in_(["queued", "running"]))).all())

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


def _name_aliases(name: str | None, layout: str = "", type_line: str = "") -> set[str]:
    raw = (name or "").strip().lower()
    if not raw:
        return set()
    aliases = {raw}
    if "//" in raw and layout != "art_series" and type_line.strip().lower() != "card":
        aliases.update(part.strip() for part in raw.split("//") if part.strip())
    return aliases
