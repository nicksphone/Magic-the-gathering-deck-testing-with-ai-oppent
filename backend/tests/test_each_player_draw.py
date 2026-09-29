"""Each-player draw instructions use active-player order and one SBA check."""

from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import infer_effect_from_oracle
from rules_engine.state_based_actions import apply_state_based_actions


DECK = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]


def _game(text="Each player draws two cards.", name="Vision Skeins", active_player=1):
    state = MatchFactory.from_decks(DECK, DECK, seed=291)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = active_player
    card = CardInstance(
        id="draw-spell", name=name, owner=1, controller=1,
        zone=Zone.STACK, types=["Instant"], oracle_text=text,
    )
    return state, card


def test_vision_skeins_draws_active_player_first_even_when_other_player_casts():
    state, card = _game(active_player=2)
    key, payload = infer_effect_from_oracle(state, card, 1)
    assert key == "effect_sequence"
    assert [item["payload"]["target_player"] for item in payload["effects"]] == [2, 1]
    before = {pid: len(state.players[pid].hand) for pid in (1, 2)}
    resolve_effect(state, 1, key, payload)
    assert all(len(state.players[pid].hand) == before[pid] + 2 for pid in (1, 2))
    draws = [line for line in state.log if line.endswith("draws 1.")]
    assert draws[-4:] == ["Player B draws 1."] * 2 + ["Player A draws 1."] * 2


def test_prosperity_x_draws_both_players_then_simultaneous_deckout():
    state, card = _game("Each player draws X cards.", "Prosperity")
    for player in state.players.values():
        player.library = player.library[:1]
    key, payload = infer_effect_from_oracle(state, card, 1, {"x_value": 2})
    assert key == "effect_sequence"
    assert [item["payload"]["amount"] for item in payload["effects"]] == [2, 2]
    resolve_effect(state, 1, key, payload)
    assert state.winner is None
    assert state.failed_draw_players == {1, 2}
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    apply_state_based_actions(restored)
    assert restored.winner == 0
    assert sum("attempted to draw from empty library" in line for line in restored.log) == 2


def test_one_empty_library_does_not_prevent_other_players_draw():
    state, card = _game(active_player=2)
    state.players[2].library.clear()
    before = len(state.players[1].hand)
    key, payload = infer_effect_from_oracle(state, card, 1)
    resolve_effect(state, 1, key, payload)
    assert state.failed_draw_players == {2}
    assert len(state.players[1].hand) == before + 2
    apply_state_based_actions(state)
    assert state.winner == 1


def test_dredge_choice_resumes_remaining_draws_and_other_player():
    state, card = _game()
    dredger = CardInstance(
        id="stinkweed", name="Stinkweed Imp", owner=1, controller=1,
        zone=Zone.GRAVEYARD, types=["Creature"], oracle_text="Dredge 5",
    )
    state.cards[dredger.id] = dredger
    state.players[1].graveyard.append(dredger.id)
    before = {pid: len(state.players[pid].hand) for pid in (1, 2)}
    key, payload = infer_effect_from_oracle(state, card, 1)
    resolve_effect(state, 1, key, payload)
    assert state.pending_mechanic_choice["player_id"] == 1
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    engine = RulesEngine()
    for _ in range(2):
        assert state.pending_mechanic_choice["player_id"] == 1
        engine.take_action(state, 1, {"type": "choose_mechanic", "choice_id": "draw"}, reject_invalid=True)
    assert state.pending_mechanic_choice is None
    assert len(state.players[1].hand) == before[1] + 2
    assert len(state.players[2].hand) == before[2] + 2


def test_vision_skeins_on_stack_draws_game_after_both_libraries_empty():
    state, _ = _game()
    state.step = Step.PRECOMBAT_MAIN
    for player in state.players.values():
        player.library.clear()
    cid = state.players[1].hand[0]
    card = state.cards[cid]
    card.name = "Vision Skeins"
    card.types = ["Instant"]
    card.type_line = "Instant"
    card.mana_cost = "{1}{U}"
    card.oracle_text = "Each player draws two cards."
    state.players[1].mana_pool = {"C": 1, "U": 1}
    engine = RulesEngine()
    engine.take_action(state, 1, {"type": "cast_spell", "card_id": cid}, reject_invalid=True)
    assert len(state.stack) == 1
    engine.take_action(state, 1, {"type": "pass_priority"}, reject_invalid=True)
    engine.take_action(state, 2, {"type": "pass_priority"}, reject_invalid=True)
    assert state.winner == 0
    assert state.cards[cid].zone == Zone.GRAVEYARD
