from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from card_data.hydration import hydrate_deck_cards
from scripts import oracle_corpus_report as report


class LocalRepository:
    def __init__(self, cached=None, knowledge=None):
        self.cached = cached or {}
        self.knowledge = knowledge or {}

    def get_cached_cards_by_names(self, names):
        return {name.casefold(): self.cached[name.casefold()]
                for name in names if name.casefold() in self.cached}

    def get_card_knowledge_by_names(self, names):
        return {name.casefold(): self.knowledge[name.casefold()]
                for name in names if name.casefold() in self.knowledge}


def corpus(monkeypatch, names):
    monkeypatch.setattr(report, "collect_corpus", lambda: {
        name.casefold(): {"name": name, "copies": count, "decks": ["test"], "sources": ["builtin"]}
        for name, count in names
    })
    monkeypatch.setattr(report, "init_db", lambda: (_ for _ in ()).throw(
        AssertionError("Injected read-only repositories must not initialize a database")))


def test_report_consumes_verified_local_knowledge_without_cache(monkeypatch):
    raw = json.loads((Path(__file__).parent / "fixtures/opaque_selection/memory-deluge.json").read_text())
    row = SimpleNamespace(name=raw["name"], scryfall_id=raw["id"], oracle_source="scryfall",
                          profiles_json=json.dumps({"card_data": raw}))
    repo = LocalRepository(knowledge={raw["name"].casefold(): row})
    corpus(monkeypatch, [(raw["name"], 4)])
    result = report.analyze_corpus(repo)
    card = result["cards"][0]
    assert card["oracle_source"] == "local_knowledge"
    assert "local_knowledge" in card["card_data_sources"]
    assert card["cached"] is False and card["ready_for_match"] is True
    assert card["oracle_preview"] == " ".join(raw["oracle_text"].split())[:240]
    assert result["corpus"]["total_copies"] == 4
    assert card["semantics_verified"] is False
    assert result["scope"]["semantics_verified"] is False


def test_report_preserves_hydrated_faces_and_runtime_factory_facts(monkeypatch):
    repo = LocalRepository()
    corpus(monkeypatch, [("Delver of Secrets", 4)])
    expected = hydrate_deck_cards(repo, [{"card_name": "Delver of Secrets", "quantity": 1}])[0]
    seen = []
    original = report.build_ability_spec

    def capture(state, card, controller):
        seen.append(card)
        assert state.cards[card.id] is card
        return original(state, card, controller)

    monkeypatch.setattr(report, "build_ability_spec", capture)
    result = report.analyze_corpus(repo)
    assert len(seen) == 1
    assert seen[0].card_faces == expected["card_faces"]
    assert seen[0].layout == expected["layout"]
    assert seen[0].power == 1 and seen[0].toughness == 1
    assert [face["name"] for face in result["cards"][0]["faces"]] == [
        face["name"] for face in expected["card_faces"]]
    assert all(face["semantics_verified"] is False for face in result["cards"][0]["faces"])


def test_report_does_not_certify_static_or_empty_oracle(monkeypatch):
    # Canonical vanilla creature: an empty Oracle field is not a missing record.
    row = SimpleNamespace(name="Savannah Lions", type_line="Creature - Cat", oracle_text="",
                          mana_cost="{W}", power="2", toughness="1")
    corpus(monkeypatch, [("Savannah Lions", 3)])
    result = report.analyze_corpus(LocalRepository(cached={"savannah lions": row}))
    assert result["cards"][0]["status"] == "static_or_noop"
    assert result["cards"][0]["semantics_verified"] is False
    assert result["cards"][0]["ready_for_match"] is True
    assert result["status_weighted"]["static_or_noop"] == 3


def test_empty_corpus_is_reported_without_constructing_a_game(monkeypatch):
    corpus(monkeypatch, [])
    monkeypatch.setattr(report.MatchFactory, "from_decks", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("Empty diagnostics need no game")))
    result = report.analyze_corpus(LocalRepository())
    assert result["cards"] == []
    assert result["highest_impact_unresolved"] == []
    assert result["status_unique"] == {}
    assert result["corpus"]["total_copies"] == 0
