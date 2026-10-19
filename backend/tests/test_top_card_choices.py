import json
import random

from card_data.sync import ScryfallSyncService
from tests.library_canonical_fixtures import canonical_card, canonicalize_basics, ranking_raw_card, raw_card, reprint
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.ability_model import build_ability_spec
from rules_engine.cast_choice import build_cast_hints, validate_cast_choice
from effects.registry import resolve_effect
from ai.agent import AIAgent
from rules_engine.engine import RulesEngine


def _iteration_birth_state(top_names=('Preordain', 'Divination', 'Explore')):
    def row(name, quantity=1):
        raw = raw_card(name) if name == 'Forest' else ranking_raw_card(name)
        cached = ScryfallSyncService._normalize_payload(
            raw, ScryfallSyncService._extract_remote_image_uri(raw))
        return {**raw, **cached, 'card_name': raw['name'], 'quantity': quantity,
                'colors': raw['colors'], 'card_faces': json.loads(cached['card_faces_json'])}

    # Arrange data before the real shuffle without advancing the game's RNG.
    permutation = list(range(60))
    random.Random(21).shuffle(permutation)
    names = ['Forest'] * 60
    for position, name in zip((51, 52, 53), top_names):
        names[permutation[position - 1]] = name
    return MatchFactory.from_decks([row(name) for name in names], [row('Forest', 60)], seed=21)


def test_top_three_hand_exile_bottom_choice_has_temporary_play_permission() -> None:
    state = _iteration_birth_state()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    player = state.players[1]
    ids = player.library[-3:]
    spell = canonical_card("Expressive Iteration", id="iteration", owner=1, controller=1, zone=Zone.HAND)
    state.cards[spell.id] = spell
    spec = build_ability_spec(state, spell, 1)
    assert spec.effect.key == "look_top_choose"
    resolve_effect(state, 1, spec.effect.key, spec.effect.payload)

    assert ids[1] in player.hand
    assert ids[2] in player.exile
    assert player.exile_play_until[ids[2]] == state.turn
    assert ids[0] in player.library


def test_ai_top_three_choice_uses_resolution_time_cards() -> None:
    state = _iteration_birth_state(('Tidings', 'Preordain', 'Explore'))
    state.pregame_pending = False
    state.mechanic_choice_players = {1}
    ids = state.players[1].library[-3:]
    resolve_effect(state, 1, "look_top_choose", {"top_n": 3})
    assert state.pending_mechanic_choice["kind"] == "look_top_choose"
    action = AIAgent(archetype="Control").choose_action(state, RulesEngine().legal_moves(state, 1), 1).action
    assert action["card_ids"][:2] == [ids[1], ids[2]]
    RulesEngine().take_action(state, 1, action, reject_invalid=True)
    assert ids[1] in state.players[1].hand
    assert ids[2] in state.players[1].exile
    assert state.pending_mechanic_choice is None


def test_top_three_choice_accepts_explicit_human_order() -> None:
    from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
    from rules_engine.engine import RulesEngine
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Forest"}],
        [{"quantity": 60, "card_name": "Forest"}],
        seed=22,
    )
    canonicalize_basics(state)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    player = state.players[1]
    ids = player.library[-3:]
    spell = canonical_card("Expressive Iteration", id="iteration-explicit", owner=1, controller=1, zone=Zone.HAND)
    state.cards[spell.id] = spell
    hints = build_cast_hints(state, spell, 1)
    assert hints["top_choice"] == {"top_n": 3}
    assert not any(cid in str(hints) for cid in ids)
    spec = build_ability_spec(state, spell, 1)
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    resolve_effect(state, 1, spec.effect.key, spec.effect.payload)
    assert state.pending_mechanic_choice["kind"] == "look_top_choose"
    assert player.library[-3:] == ids
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    RulesEngine().take_action(restored, 1, {"type": "choose_mechanic", "card_ids": [ids[0], ids[2], ids[1]]}, reject_invalid=True)
    assert ids[0] in restored.players[1].hand
    assert ids[2] in restored.players[1].exile
    assert restored.players[1].library[0] == ids[1]
    assert restored.players[1].exile_play_until[ids[2]] == restored.turn


def test_expressive_iteration_wording_with_exile_verb_is_structured() -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Forest"}],
        [{"quantity": 60, "card_name": "Forest"}],
        seed=24,
    )
    canonicalize_basics(state)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    spell = canonical_card("Expressive Iteration", id="iteration-modern-wording", owner=1, controller=1, zone=Zone.HAND)
    state.cards[spell.id] = spell

    spec = build_ability_spec(state, spell, 1)

    assert spec.effect.key == "look_top_choose"
    assert spec.used_fallback is False


def test_top_three_choice_rejects_duplicate_or_missing_cards() -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Forest"}],
        [{"quantity": 60, "card_name": "Forest"}],
        seed=23,
    )
    canonicalize_basics(state)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    spell = canonical_card("Expressive Iteration", id="iteration-invalid", owner=1, controller=1, zone=Zone.HAND)
    state.cards[spell.id] = spell
    hints = build_cast_hints(state, spell, 1)
    ids = state.players[1].library[-3:]
    ok, error = validate_cast_choice(
        hints,
        {
            "top_choice_hand_id": ids[0],
            "top_choice_exile_id": ids[0],
            "top_choice_bottom_ids": [ids[1]],
        },
    )
    assert ok is False
    assert "when the effect resolves" in error.lower()
    from rules_engine.action_validation import ActionRejected
    from rules_engine.engine import RulesEngine
    import pytest
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    resolve_effect(state, 1, "look_top_choose", {"top_n": 3})
    with pytest.raises(ActionRejected):
        RulesEngine().take_action(state, 1, {"type": "choose_mechanic", "card_ids": [ids[0], ids[0], ids[1]]}, reject_invalid=True)
    assert state.pending_mechanic_choice


def test_iteration_uses_resolution_library_and_turn_after_stack_resume() -> None:
    from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
    from rules_engine.engine import RulesEngine
    from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack

    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Forest"}],
        [{"quantity": 60, "card_name": "Forest"}], seed=25,
    )
    canonicalize_basics(state)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    player = state.players[1]
    spell = canonical_card("Expressive Iteration", id="iteration-stack", owner=1, controller=1, zone=Zone.STACK)
    state.cards[spell.id] = spell
    spec = build_ability_spec(state, spell, 1)
    assert "play_exiled_until" not in spec.effect.payload
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    add_to_stack(state, spell.id, 1, spell.name, spec.effect.key, spec.effect.payload)
    old_top = player.library.pop()
    player.library.insert(0, old_top)
    actual_top = player.library[-3:]
    state.turn = 2
    resolve_top_of_stack(state)
    assert state.pending_mechanic_choice["top_ids"] == actual_top
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    RulesEngine().take_action(restored, 1, {"type": "choose_mechanic", "card_ids": [actual_top[0], actual_top[2], actual_top[1]]}, reject_invalid=True)
    assert actual_top[0] in restored.players[1].hand
    assert actual_top[2] in restored.players[1].exile
    assert restored.players[1].exile_play_until[actual_top[2]] == 2
    assert restored.players[1].library[0] == actual_top[1]
    assert spell.id in restored.players[1].graveyard
    assert not restored.stack


def test_http_iteration_choice_exposes_ordered_options_at_resolution() -> None:
    from fastapi.testclient import TestClient
    from main import ACTIVE_MATCHES, MatchController, app
    from rules_engine.engine import RulesEngine

    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Forest"}],
        [{"quantity": 60, "card_name": "Forest"}], seed=26,
    )
    canonicalize_basics(state)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    ids = state.players[1].library[-3:]
    resolve_effect(state, 1, "look_top_choose", {"top_n": 3})
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
            assert move["kind"] == "look_top_choose" and move["count"] == 3
            assert set(move["options"]) == set(ids)
            response = client.post(f"/matches/{state.id}/action", json={
                "player_id": 1, "action": {"type": "choose_mechanic", "card_ids": [ids[2], ids[0], ids[1]]},
            })
            assert response.status_code == 200
            assert response.json()["pending_mechanic_choice"] is None
            assert any(card["id"] == ids[2] for card in response.json()["players"]["1"]["hand"])
            assert ids[0] in match.state.players[1].exile
        finally:
            ACTIVE_MATCHES.pop(state.id, None)
