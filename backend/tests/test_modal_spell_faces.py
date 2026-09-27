"""Canonical MDFCs test selected spell identity, not full Oracle certification."""
import json
from pathlib import Path
from types import SimpleNamespace

from card_data.hydration import hydrate_deck_cards
from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Step, Zone
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.engine import RulesEngine
from rules_engine.card_faces import select_cast_face
from rules_engine.stack_engine import resolve_top_of_stack

DATA = json.loads((Path(__file__).parent / "fixtures/modal_spell_faces.json").read_text())
ARCHAIC = "Wandering Archaic // Explore the Vastlands"
VALKI = "Valki, God of Lies // Tibalt, Cosmic Impostor"


def fixture(name):
    raw = DATA[name]
    row = SimpleNamespace(**{key: value for key, value in raw.items() if key != "card_faces"},
                          card_faces_json=json.dumps(raw["card_faces"]), image_uri="/card-images/offline.svg")
    repo = SimpleNamespace(get_cached_cards_by_names=lambda names: {name.lower(): row})
    deck = hydrate_deck_cards(repo, [{"quantity": 60, "card_name": name}])
    game = MatchFactory.from_decks(deck, deck, seed=9)
    game.pregame_pending = False
    game.kept_hands = {1, 2}
    game.step = Step.PRECOMBAT_MAIN
    game.players[1].mana_pool.update({color: 20 for color in "WUBRGC"})
    return game, game.cards[game.players[1].hand[0]]


def test_layout_and_front_characteristics_survive_hydration_snapshot():
    game, card = fixture(ARCHAIC)
    assert card.layout == "modal_dfc"
    assert card.types == ["Creature"]
    assert card.mana_cost == "{5}"
    restored = deserialize_match_snapshot(serialize_match_snapshot(game))
    assert restored.cards[card.id].layout == "modal_dfc"


def test_selected_sorcery_uses_its_cost_and_resolves_to_graveyard_then_restores():
    game, card = fixture(ARCHAIC)
    game.players[1].mana_pool = {color: 0 for color in "WUBRGC"}
    game.players[1].mana_pool["C"] = 3
    rules = RulesEngine()
    moves = rules.legal_moves(game, 1)
    assert any(move.get("selected_face_index") == 1 for move in moves)
    rules.take_action(game, 1, {"type": "cast_spell", "card_id": card.id, "selected_face_index": 1}, reject_invalid=True)
    assert card.types == ["Sorcery"]
    assert card.name == "Explore the Vastlands"
    assert card.mana_cost == "{3}"
    assert sum(game.players[1].mana_pool.values()) == 0
    restored = deserialize_match_snapshot(serialize_match_snapshot(game))
    resolve_top_of_stack(restored)
    resolved = restored.cards[card.id]
    assert resolved.zone == Zone.GRAVEYARD
    assert resolved.types == ["Creature"]
    assert resolved.mana_cost == "{5}"
    assert not resolved.printed_characteristics


def test_selected_planeswalker_has_its_own_stats_and_survives_snapshot():
    game, card = fixture(VALKI)
    RulesEngine().take_action(game, 1, {"type": "cast_spell", "card_id": card.id, "selected_face_index": 1}, reject_invalid=True)
    assert card.types == ["Planeswalker"]
    assert card.power is None and card.toughness is None
    assert card.loyalty == 5
    restored = deserialize_match_snapshot(serialize_match_snapshot(game))
    resolve_top_of_stack(restored)
    assert restored.cards[card.id].zone == Zone.BATTLEFIELD
    assert restored.cards[card.id].name == "Tibalt, Cosmic Impostor"
    assert restored.cards[card.id].loyalty == 5


def test_face_proxy_does_not_retain_front_creature_stats_or_types():
    _, card = fixture(ARCHAIC)
    face = select_cast_face(card, 1)
    assert face.types == ["Sorcery"] and face.power is None
    assert card.types == ["Creature"] and card.power == 4


def test_sync_preserves_layout_and_face_loyalty_without_network():
    service = object.__new__(ScryfallSyncService)
    raw = DATA[VALKI]
    normalized = service._normalize_payload(raw, "/card-images/offline.svg")
    assert normalized["layout"] == "modal_dfc"
    assert json.loads(normalized["card_faces_json"])[1]["loyalty"] == "5"


def test_checked_api_action_accepts_only_the_affordable_modal_face():
    from rules_engine.action_validation import validate_action, ActionRejected
    import pytest
    game, card = fixture(ARCHAIC)
    game.players[1].mana_pool = {color: 0 for color in "WUBRGC"}
    game.players[1].mana_pool["C"] = 3
    rules = RulesEngine()
    validate_action(game, rules, 1, {"type": "cast_spell", "card_id": card.id, "selected_face_index": 1})
    with pytest.raises(ActionRejected):
        validate_action(game, rules, 1, {"type": "cast_spell", "card_id": card.id, "selected_face_index": 0})


def test_ai_materializes_the_offered_face_without_overriding_its_identity():
    from ai.agent import AIAgent
    game, card = fixture(ARCHAIC)
    game.players[1].mana_pool = {color: 0 for color in "WUBRGC"}
    game.players[1].mana_pool["C"] = 3
    rules = RulesEngine()
    move = next(move for move in rules.legal_moves(game, 1) if move.get("selected_face_index") == 1)
    action = AIAgent()._materialize_action(game, move, 1)
    assert action["selected_face_index"] == 1
    rules.take_action(game, 1, action, reject_invalid=True)
    assert card.types == ["Sorcery"] and card.zone == Zone.STACK


def test_legacy_cache_layout_migration_preserves_rows_and_is_repeatable(tmp_path, monkeypatch):
    import persistence.db as db
    from sqlmodel import create_engine
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE cardcache (name TEXT)")
        conn.exec_driver_sql("INSERT INTO cardcache VALUES ('Wandering Archaic // Explore the Vastlands')")
    monkeypatch.setattr(db, "engine", engine)
    db._ensure_card_cache_columns()
    db._ensure_card_cache_columns()
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT name, layout FROM cardcache").one() == (ARCHAIC, "")
    engine.dispose()


def test_transform_back_is_not_a_modal_cast_choice():
    from rules_engine.action_validation import validate_action, ActionRejected
    from ai.agent import AIAgent
    import pytest
    game, card = fixture("Delver of Secrets // Insectile Aberration")
    assert card.layout == "transform"
    assert len(AIAgent()._modal_face_options(card)) == 1
    before = serialize_match_snapshot(game)
    with pytest.raises(ActionRejected, match="cannot be cast directly"):
        validate_action(game, RulesEngine(), 1, {"type": "cast_spell", "card_id": card.id, "selected_face_index": 1})
    assert serialize_match_snapshot(game) == before
