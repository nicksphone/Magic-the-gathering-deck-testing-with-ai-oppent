from __future__ import annotations

from collections import Counter
from typing import Any

from persistence.repository import Repository


class TournamentIngestService:
    """Ingest external tournament event payloads into normalized local tables.

    Expected payload format:
    {
      "source": "mtgtop8",
      "event": {
        "external_id": "event-123",
        "name": "RCQ Springfield",
        "format": "modern",
        "event_date": "2026-05-01",
        "url": "https://...",
        "metadata": {...}
      },
      "decks": [
        {
          "player_name": "Alice",
          "archetype": "Burn",
          "placement": 1,
          "wins": 8,
          "losses": 1,
          "draws": 0,
          "mainboard": [{"quantity": 4, "card_name": "Lightning Bolt"}],
          "sideboard": [{"quantity": 2, "card_name": "Roiling Vortex"}],
          "metadata": {...}
        }
      ]
    }
    """

    def __init__(self, repo: Repository):
        self.repo = repo

    def ingest_event_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        source = str(payload.get("source", "unknown")).strip() or "unknown"
        event = payload.get("event") or {}
        decks = list(payload.get("decks") or [])

        if not event:
            raise ValueError("event block is required")
        if not decks:
            raise ValueError("decks list is required and cannot be empty")

        ext_id = str(event.get("external_id", "")).strip() or self._fallback_event_id(source, event)
        evt = self.repo.upsert_tournament_event(
            external_id=ext_id,
            source=source,
            name=str(event.get("name", "Unnamed Event")),
            format=str(event.get("format", "unknown")),
            event_date=str(event.get("event_date", "")),
            url=str(event.get("url", "")),
            metadata=event.get("metadata") or {},
        )

        normalized_decks = [self._normalize_deck(d, idx=i + 1) for i, d in enumerate(decks)]
        inserted = self.repo.replace_tournament_event_decks(event_id=int(evt.id), decks=normalized_decks)

        archetypes = Counter(d.get("archetype", "unknown") for d in normalized_decks)
        return {
            "event_id": evt.id,
            "event_name": evt.name,
            "source": evt.source,
            "inserted_decks": inserted,
            "archetypes": dict(archetypes),
        }

    def summarize_event(self, event_id: int) -> dict[str, Any]:
        rows = self.repo.list_tournament_decks(event_id)
        if not rows:
            return {
                "event_id": event_id,
                "deck_count": 0,
                "archetypes": {},
                "top8": [],
            }
        arche = Counter((r.archetype or "unknown") for r in rows)
        top8 = [
            {
                "placement": r.placement,
                "player_name": r.player_name,
                "archetype": r.archetype,
                "record": f"{r.wins}-{r.losses}-{r.draws}",
            }
            for r in rows
            if int(r.placement or 0) > 0
        ]
        top8.sort(key=lambda x: x["placement"])
        return {
            "event_id": event_id,
            "deck_count": len(rows),
            "archetypes": dict(arche),
            "top8": top8[:8],
        }

    def _normalize_deck(self, deck: dict[str, Any], idx: int) -> dict[str, Any]:
        main = [self._normalize_card_item(x) for x in list(deck.get("mainboard") or [])]
        side = [self._normalize_card_item(x) for x in list(deck.get("sideboard") or [])]
        main_total = sum(x["quantity"] for x in main)
        if main_total < 60:
            raise ValueError(
                f"Deck #{idx} ({deck.get('player_name', 'unknown')}): mainboard has {main_total} cards; minimum is 60"
            )
        return {
            "player_name": str(deck.get("player_name", f"Player {idx}")),
            "archetype": str(deck.get("archetype", "unknown")),
            "placement": int(deck.get("placement", 0) or 0),
            "wins": int(deck.get("wins", 0) or 0),
            "losses": int(deck.get("losses", 0) or 0),
            "draws": int(deck.get("draws", 0) or 0),
            "mainboard": main,
            "sideboard": side,
            "metadata": deck.get("metadata") or {},
        }

    def _normalize_card_item(self, item: dict[str, Any]) -> dict[str, Any]:
        qty = int(item.get("quantity", 0) or 0)
        name = str(item.get("card_name", "")).strip()
        if qty <= 0 or not name:
            raise ValueError(f"Invalid card item: {item}")
        return {"quantity": qty, "card_name": name}

    def _fallback_event_id(self, source: str, event: dict[str, Any]) -> str:
        name = str(event.get("name", "event")).strip().lower().replace(" ", "-")
        date = str(event.get("event_date", "")).strip()
        return f"{source}:{name}:{date}"
