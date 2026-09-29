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
from rules_engine.events import emit_event
from game_state.state import assign_static_order_on_battlefield_entry
from rules_engine.action_validation import ActionRejected, checked_action
from effects.registry import resolve_effect

DATA = json.loads((Path(__file__).parent / "fixtures/modal_spell_faces.json").read_text())
ARCHAIC = "Wandering Archaic // Explore the Vastlands"
VALKI = "Valki, God of Lies // Tibalt, Cosmic Impostor"


def _valki_entry():
    state, source = fixture(VALKI)
    state.players[1].hand.remove(source.id)
    state.players[1].battlefield.append(source.id)
    source.move_to_zone(Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, source.id)
    emit_event(state, "enters_battlefield", {"card_id": source.id, "controller": 1})
    assert state.stack[-1].effect_key == "choose_revealed_exile"
    return state, source


def test_valki_reveal_exiles_creature_then_returns_it_to_owner_hand() -> None:
    state, source = _valki_entry()
    state.mechanic_choice_players = {1}
    creature = state.players[2].hand[0]
    noncreature = state.players[2].hand[1]
    state.cards[noncreature].types = ["Sorcery"]
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice["options"] == [cid for cid in state.players[2].hand if cid != noncreature]
    before = serialize_match_snapshot(state)
    try:
        checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": [noncreature]})
    except ActionRejected:
        pass
    else:
        raise AssertionError("Noncreature was accepted for Valki's reveal")
    assert serialize_match_snapshot(state) == before
    state = deserialize_match_snapshot(before)
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": [creature]})
    assert state.cards[creature].zone == Zone.EXILE
    assert state.linked_exiles[0]["return_zone"] == "hand"
    resolve_effect(state, 2, "destroy_permanent", {"target_card_id": source.id})
    assert state.cards[creature].zone == Zone.HAND
    assert creature in state.players[2].hand
    assert not state.linked_exiles


def test_valki_source_leaves_before_trigger_resolves_still_reveals_without_exiling() -> None:
    state, source = _valki_entry()
    before = list(state.players[2].hand)
    resolve_effect(state, 2, "return_permanent_to_hand", {"target_card_id": source.id})
    assert resolve_top_of_stack(state)
    assert state.players[2].hand == before
    assert any("reveals their hand" in line for line in state.log)
    assert not state.linked_exiles


def test_valki_automatic_choice_and_old_source_incarnation() -> None:
    state, source = _valki_entry()
    assert resolve_top_of_stack(state)
    assert len(state.linked_exiles) == 1
    held = state.linked_exiles[0]["card_ids"][0]
    old_timestamp = source.effect_timestamp
    resolve_effect(state, 2, "return_permanent_to_hand", {"target_card_id": source.id})
    assert state.cards[held].zone == Zone.HAND
    state.players[1].hand.remove(source.id)
    state.players[1].battlefield.append(source.id)
    source.move_to_zone(Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, source.id)
    assert source.effect_timestamp != old_timestamp
    assert not state.linked_exiles


def test_valki_old_trigger_does_not_exile_after_source_reenters() -> None:
    state, source = _valki_entry()
    original_hand = list(state.players[2].hand)
    resolve_effect(state, 2, "return_permanent_to_hand", {"target_card_id": source.id})
    state.players[1].hand.remove(source.id)
    state.players[1].battlefield.append(source.id)
    source.move_to_zone(Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, source.id)
    assert resolve_top_of_stack(state)
    assert state.players[2].hand == original_hand
    assert not state.linked_exiles


def test_valki_old_link_does_not_return_card_that_left_exile() -> None:
    from rules_engine.linked_exile import flush_linked_exile_returns

    state, source = _valki_entry()
    assert resolve_top_of_stack(state)
    held = state.linked_exiles[0]["card_ids"][0]
    card = state.cards[held]
    state.players[2].exile.remove(held)
    state.players[2].graveyard.append(held)
    card.move_to_zone(Zone.GRAVEYARD)
    flush_linked_exile_returns(state)
    assert not state.linked_exiles
    resolve_effect(state, 2, "destroy_permanent", {"target_card_id": source.id})
    assert card.zone == Zone.GRAVEYARD


def test_valki_ai_chooses_a_revealed_creature_through_legal_moves() -> None:
    from ai.agent import AIAgent

    state, source = _valki_entry()
    state.mechanic_choice_players = {1, 2}
    assert not resolve_top_of_stack(state)
    legal = RulesEngine().legal_moves(state, 1)
    action = AIAgent(difficulty="master", archetype="Control").choose_action(state, legal, 1).action
    assert action["type"] == "choose_mechanic"
    assert action["card_ids"][0] in state.pending_mechanic_choice["options"]
    state = checked_action(state, RulesEngine(), 1, action)
    assert state.cards[action["card_ids"][0]].zone == Zone.EXILE
    resolve_effect(state, 2, "destroy_permanent", {"target_card_id": source.id})
    assert state.cards[action["card_ids"][0]].zone == Zone.HAND


def test_valki_http_choice_persists_link_and_returns_to_hand() -> None:
    from fastapi.testclient import TestClient
    from main import ACTIVE_MATCHES, MatchController, app

    state, source = _valki_entry()
    state.mechanic_choice_players = {1, 2}
    assert not resolve_top_of_stack(state)
    deck = [{"quantity": 60, "card_name": VALKI}]
    match = MatchController(
        state=state, rules=RulesEngine(), controllers={1: "human", 2: "ai"}, ai={},
        mode="player_vs_ai", deck_ids=(None, None), mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3,
    )
    with TestClient(app) as client:
        ACTIVE_MATCHES[state.id] = match
        try:
            move = client.get(f"/matches/{state.id}/legal-moves").json()["moves"][0]
            assert move["kind"] == "choose_revealed_exile"
            chosen = move["options"][0]
            response = client.post(f"/matches/{state.id}/action", json={
                "player_id": 1, "action": {"type": "choose_mechanic", "card_ids": [chosen]},
            })
            assert response.status_code == 200
            assert ACTIVE_MATCHES[state.id].state.linked_exiles[0]["card_ids"] == [chosen]
            restored = deserialize_match_snapshot(serialize_match_snapshot(ACTIVE_MATCHES[state.id].state))
            resolve_effect(restored, 2, "destroy_permanent", {"target_card_id": source.id})
            assert restored.cards[chosen].zone == Zone.HAND
        finally:
            ACTIVE_MATCHES.pop(state.id, None)


def _valki_with_exiled_mystic():
    from card_data.fallback_cards import fallback_card_payload

    state, source = _valki_entry()
    state.mechanic_choice_players = {1, 2}
    target_id = state.players[2].hand[0]
    printed = fallback_card_payload("Elvish Mystic")
    assert printed is not None
    target = state.cards[target_id]
    target.name = printed["name"]
    target.type_line = printed["type_line"]
    target.types = ["Creature"]
    target.mana_cost = printed["mana_cost"]
    target.oracle_text = printed["oracle_text"]
    target.power = int(printed["power"])
    target.toughness = int(printed["toughness"])
    target.card_faces = []
    target.layout = ""
    assert not resolve_top_of_stack(state)
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": [target_id]})
    state.players[1].mana_pool = {color: 0 for color in "WUBRGC"}
    state.players[1].mana_pool["B"] = 1
    return state, source.id, target_id


def test_variable_activated_cost_rejects_missing_or_unaffordable_x_before_mutation() -> None:
    state, source_id, _ = _valki_with_exiled_mystic()
    moves = [move for move in RulesEngine().legal_moves(state, 1) if move["type"] == "activate_ability"]
    assert len(moves) == 1 and moves[0]["mana_cost"] == "{X}"
    assert moves[0]["target_hints"]["requires_x_value"]
    before = serialize_match_snapshot(state)
    for targets in ({}, {"x_value": -1}, {"x_value": 2}, {"x_value": 1.5}):
        try:
            checked_action(state, RulesEngine(), 1, {
                "type": "activate_ability", "card_id": source_id,
                "ability_index": 0, "targets": targets,
            })
        except ActionRejected:
            pass
        else:
            raise AssertionError(f"Invalid variable activation was accepted: {targets}")
        assert serialize_match_snapshot(state) == before


def test_valki_copy_ability_uses_announced_x_and_restores_printed_characteristics() -> None:
    from rules_engine.oracle_effects import extract_activated_abilities

    state, source_id, target_id = _valki_with_exiled_mystic()
    state = checked_action(state, RulesEngine(), 1, {
        "type": "activate_ability", "card_id": source_id,
        "ability_index": 0, "targets": {"x_value": 1},
    })
    assert state.players[1].mana_pool["B"] == 0
    assert state.stack[-1].effect_key == "copy_linked_exiled_card"
    assert state.cards[source_id].name == "Valki, God of Lies // Tibalt, Cosmic Impostor"
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice["kind"] == "linked_exile_copy"
    assert state.pending_mechanic_choice["options"] == [target_id]
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": [target_id]})
    copied = state.cards[source_id]
    assert copied.name == "Elvish Mystic"
    assert copied.oracle_text == "{T}: Add {G}."
    assert copied.types == ["Creature"] and copied.power == copied.toughness == 1
    assert not extract_activated_abilities(copied)
    assert copied.summoning_sick
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    resolve_effect(state, 2, "destroy_permanent", {"target_card_id": source_id})
    assert state.cards[source_id].name == VALKI
    assert state.cards[source_id].zone == Zone.GRAVEYARD
    assert state.cards[target_id].zone == Zone.HAND
    assert not state.cards[source_id].printed_characteristics


def test_valki_ai_announces_the_exiled_cards_mana_value_not_all_available_mana() -> None:
    from ai.agent import AIAgent

    state, source_id, target_id = _valki_with_exiled_mystic()
    state.players[1].mana_pool = {color: 20 for color in "WUBRGC"}
    move = next(move for move in RulesEngine().legal_moves(state, 1) if move["type"] == "activate_ability")
    action = AIAgent(difficulty="master")._materialize_action(state, move, 1)
    assert action["targets"]["x_value"] == 1
    assert not action.get("_invalid_ai_choice")
    state = checked_action(state, RulesEngine(), 1, action)
    assert not resolve_top_of_stack(state)
    decision = AIAgent(difficulty="master").choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action["card_ids"] == [target_id]


def test_valki_copy_ability_does_nothing_if_source_left_before_resolution() -> None:
    state, source_id, target_id = _valki_with_exiled_mystic()
    state = checked_action(state, RulesEngine(), 1, {
        "type": "activate_ability", "card_id": source_id,
        "ability_index": 0, "targets": {"x_value": 1},
    })
    resolve_effect(state, 2, "destroy_permanent", {"target_card_id": source_id})
    assert state.cards[target_id].zone == Zone.HAND
    assert resolve_top_of_stack(state)
    assert state.pending_mechanic_choice is None
    assert state.cards[source_id].zone == Zone.GRAVEYARD


def test_two_copy_activations_on_stack_resolve_after_source_loses_ability() -> None:
    state, source_id, target_id = _valki_with_exiled_mystic()
    state.players[1].mana_pool["B"] = 2
    for _ in range(2):
        state = checked_action(state, RulesEngine(), 1, {
            "type": "activate_ability", "card_id": source_id,
            "ability_index": 0, "targets": {"x_value": 1},
        })
    assert len(state.stack) == 2
    for _ in range(2):
        assert not resolve_top_of_stack(state)
        state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": [target_id]})
        assert state.cards[source_id].name == "Elvish Mystic"
    assert not state.stack


def test_copy_activation_has_no_choice_if_linked_card_left_exile() -> None:
    from rules_engine.linked_exile import flush_linked_exile_returns

    state, source_id, target_id = _valki_with_exiled_mystic()
    state = checked_action(state, RulesEngine(), 1, {
        "type": "activate_ability", "card_id": source_id,
        "ability_index": 0, "targets": {"x_value": 1},
    })
    held = state.cards[target_id]
    state.players[2].exile.remove(target_id)
    state.players[2].hand.append(target_id)
    held.move_to_zone(Zone.HAND)
    flush_linked_exile_returns(state)
    assert resolve_top_of_stack(state)
    assert state.pending_mechanic_choice is None
    assert state.cards[source_id].name == VALKI


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
