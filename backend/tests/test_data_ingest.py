from __future__ import annotations

from sqlmodel import Session

from data_ingest.service import TournamentIngestService
from persistence.db import engine, init_db
from persistence.repository import Repository


def _sample_payload() -> dict:
    return {
        "source": "unit-test",
        "event": {
            "external_id": "ev-1",
            "name": "Test Open",
            "format": "modern",
            "event_date": "2026-05-16",
            "url": "https://example.com/event/1",
        },
        "decks": [
            {
                "player_name": "Alice",
                "archetype": "Burn",
                "placement": 1,
                "wins": 7,
                "losses": 1,
                "draws": 0,
                "mainboard": [
                    {"quantity": 4, "card_name": "Lightning Bolt"},
                    {"quantity": 56, "card_name": "Mountain"},
                ],
                "sideboard": [{"quantity": 2, "card_name": "Roiling Vortex"}],
            },
            {
                "player_name": "Bob",
                "archetype": "Control",
                "placement": 2,
                "wins": 6,
                "losses": 2,
                "draws": 0,
                "mainboard": [
                    {"quantity": 4, "card_name": "Counterspell"},
                    {"quantity": 56, "card_name": "Island"},
                ],
                "sideboard": [{"quantity": 2, "card_name": "Mystical Dispute"}],
            },
        ],
    }


def test_ingest_tournament_event_and_summary() -> None:
    init_db()
    with Session(engine) as session:
        repo = Repository(session)
        svc = TournamentIngestService(repo)
        out = svc.ingest_event_payload(_sample_payload())
        assert out["inserted_decks"] == 2
        summary = svc.summarize_event(int(out["event_id"]))
        assert summary["deck_count"] == 2
        assert summary["archetypes"].get("Burn") == 1
        assert len(summary["top8"]) == 2


def test_ingest_rejects_short_mainboard() -> None:
    payload = _sample_payload()
    payload["decks"][0]["mainboard"] = [{"quantity": 4, "card_name": "Lightning Bolt"}]
    init_db()
    with Session(engine) as session:
        repo = Repository(session)
        svc = TournamentIngestService(repo)
        try:
            svc.ingest_event_payload(payload)
            assert False, "expected ValueError"
        except ValueError as exc:
            assert "minimum is 60" in str(exc)
