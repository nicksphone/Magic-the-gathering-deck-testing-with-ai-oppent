from ai.agent import AIAgent
from card_data.fallback_cards import fallback_card_payload
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.card_types import cards_have_distinct_card_types
from rules_engine.engine import RulesEngine
from rules_engine.events import emit_event
from rules_engine.stack_engine import resolve_top_of_stack


def _atraxa_state():
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck, seed=1994)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    source = fallback_card_payload("Atraxa, Grand Unifier")
    assert source is not None
    atraxa = CardInstance(
        "atraxa", source["name"], 1, 1, Zone.BATTLEFIELD,
        ["Creature"], oracle_text=source["oracle_text"],
    )
    state.cards[atraxa.id] = atraxa
    state.players[1].battlefield.append(atraxa.id)
    top = state.players[1].library[-10:]
    named = {
        "dual": (top[0], "Eidolon of the Great Revel"),
        "creature": (top[1], "Atraxa, Grand Unifier"),
        "enchantment": (top[2], "Temporary Lockdown"),
        "instant": (top[3], "Memory Deluge"),
        "artifact": (top[4], "Torrential Gearhulk"),
    }
    for card_id, name in named.values():
        data = fallback_card_payload(name)
        assert data is not None
        card = state.cards[card_id]
        card.name = data["name"]
        card.type_line = data["type_line"]
        card.types = data["type_line"].split(" — ")[0].split()
        card.oracle_text = data["oracle_text"]
        card.mana_cost = data["mana_cost"]
    return state, atraxa, top, {key: card_id for key, (card_id, _) in named.items()}


def _resolve_atraxa(state, atraxa):
    emit_event(state, "enters_battlefield", {"card_id": atraxa.id, "controller": 1})
    assert len(state.stack) == 1
    assert state.stack[-1].effect_key == "look_top_distinct_types_to_hand"
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice["kind"] == "topdeck_put"
    return state


def test_atraxa_reveal_requires_a_distinct_type_assignment_after_restore() -> None:
    state, atraxa, top, named = _atraxa_state()
    state = _resolve_atraxa(state, atraxa)
    invalid = [named["dual"], named["creature"], named["enchantment"]]
    valid = [named["dual"], named["creature"], named["instant"], top[5]]
    assert not cards_have_distinct_card_types(state, invalid)
    assert cards_have_distinct_card_types(state, valid)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    before = serialize_match_snapshot(state)
    try:
        checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": invalid})
    except ActionRejected:
        pass
    else:
        raise AssertionError("Impossible card-type choice was accepted")
    assert serialize_match_snapshot(state) == before
    try:
        checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": [{}]})
    except (ActionRejected, ValueError):
        pass
    else:
        raise AssertionError("Malformed card IDs were accepted")
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": valid})
    assert set(valid) <= set(state.players[1].hand)
    assert len(state.players[1].library) == 53 - len(valid)
    assert set(top) - set(valid) <= set(state.players[1].library)
    assert state.pending_mechanic_choice is None


def test_atraxa_ai_selects_only_assignable_types() -> None:
    state, atraxa, top, _ = _atraxa_state()
    state = _resolve_atraxa(state, atraxa)
    legal = RulesEngine().legal_moves(state, 1)
    chosen = AIAgent(archetype="Midrange").choose_action(state, legal, 1).action
    assert chosen["type"] == "choose_mechanic"
    assert cards_have_distinct_card_types(state, chosen["card_ids"])
    assert set(chosen["card_ids"]) <= set(top)
    state = checked_action(state, RulesEngine(), 1, chosen)
    assert set(chosen["card_ids"]) <= set(state.players[1].hand)


def test_kindred_is_an_independent_card_type_for_reveal() -> None:
    state, _, top, _ = _atraxa_state()
    kindred = state.cards[top[6]]
    kindred.name = "Summon the School"
    kindred.type_line = "Kindred Sorcery — Merfolk"
    kindred.types = ["Kindred", "Sorcery"]
    sorcery = state.cards[top[7]]
    sorcery.types = ["Sorcery"]
    assert cards_have_distinct_card_types(state, [kindred.id, sorcery.id])


def test_atraxa_ai_considers_all_revealed_cards_before_type_filter() -> None:
    state, atraxa, top, _ = _atraxa_state()
    forest = fallback_card_payload("Forest")
    instant = fallback_card_payload("Memory Deluge")
    assert forest is not None and instant is not None
    for card_id in top:
        data = instant if card_id == top[0] else forest
        card = state.cards[card_id]
        card.name = data["name"]
        card.type_line = data["type_line"]
        card.types = data["type_line"].split(" — ")[0].split()
        card.oracle_text = data["oracle_text"]
        card.mana_cost = data["mana_cost"]
    state = _resolve_atraxa(state, atraxa)
    agent = AIAgent(archetype="Midrange")
    agent._choose_library_search = lambda _state, options, count, _player_id, **_kwargs: list(options)[:count]
    chosen = agent.choose_action(state, RulesEngine().legal_moves(state, 1), 1).action["card_ids"]
    assert len(chosen) == 2
    assert top[0] in chosen


def test_atraxa_zero_selection_still_reveals_and_bottoms_cards() -> None:
    state, atraxa, top, _ = _atraxa_state()
    other = state.cards[top[5]]
    state.players[1].library.remove(other.id)
    state.players[1].battlefield.append(other.id)
    other.move_to_zone(Zone.BATTLEFIELD)
    emit_event(state, "enters_battlefield", {"card_id": other.id, "controller": 1})
    assert not state.stack
    initial_hand = len(state.players[1].hand)
    state = _resolve_atraxa(state, atraxa)
    revealed = list(state.pending_mechanic_choice["top_ids"])
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": []})
    assert len(state.players[1].hand) == initial_hand
    assert set(state.players[1].library[:len(revealed)]) == set(revealed)
    assert any("reveals" in entry and "puts 0 into hand" in entry for entry in state.log)


def test_atraxa_choice_is_validated_through_match_api() -> None:
    from fastapi.testclient import TestClient
    from main import ACTIVE_MATCHES, MatchController, app

    state, atraxa, top, named = _atraxa_state()
    state = _resolve_atraxa(state, atraxa)
    deck = [{"quantity": 60, "card_name": "Forest"}]
    match = MatchController(
        state=state, rules=RulesEngine(), controllers={1: "human", 2: "ai"}, ai={},
        mode="player_vs_ai", deck_ids=(None, None), mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3,
    )
    with TestClient(app) as client:
        ACTIVE_MATCHES[state.id] = match
        try:
            legal = client.get(f"/matches/{state.id}/legal-moves")
            assert legal.status_code == 200
            move = legal.json()["moves"][0]
            assert move["kind"] == "topdeck_put"
            assert move["count"] == 9
            assert set(move["options"]) == set(top)
            assert "Enchantment Creature" in move["option_type_lines"][named["dual"]]
            invalid = client.post(f"/matches/{state.id}/action", json={
                "player_id": 1, "action": {"type": "choose_mechanic", "card_ids": [named["dual"], named["creature"], named["enchantment"]]},
            })
            assert 400 <= invalid.status_code < 500
            valid = client.post(f"/matches/{state.id}/action", json={
                "player_id": 1, "action": {"type": "choose_mechanic", "card_ids": [named["dual"], named["creature"]]},
            })
            assert valid.status_code == 200
            assert {named["dual"], named["creature"]} <= set(ACTIVE_MATCHES[state.id].state.players[1].hand)
        finally:
            ACTIVE_MATCHES.pop(state.id, None)
