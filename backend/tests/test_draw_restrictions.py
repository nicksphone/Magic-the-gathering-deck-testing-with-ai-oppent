from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine.replacement import replacement_options
from tests.draw_canonical_sidecar import canonical_card, deck_entry


def _game():
    deck = [deck_entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck, seed=93)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    return state


def _permanent(state, cid, controller):
    card = canonical_card(
        cid, id=cid, owner=controller, controller=controller,
        zone=Zone.BATTLEFIELD,
    )
    state.cards[cid] = card
    state.players[controller].battlefield.append(cid)


def test_spirit_caps_each_players_successful_draws_before_replacements() -> None:
    state = _game()
    _permanent(state, "Spirit of the Labyrinth", 2)
    _permanent(state, "Thought Reflection", 1)
    before = len(state.players[1].hand)
    resolve_effect(state, 1, "draw_cards", {"amount": 3})
    assert len(state.players[1].hand) == before + 1
    assert state.draws_this_turn[1] == 1
    assert replacement_options(state, "card_draw", target_player=1) == []
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    resolve_effect(state, 1, "draw_cards", {"amount": 1})
    assert state.pending_replacement_choice is None
    assert len(state.players[1].hand) == before + 1


def test_narset_counts_prior_draw_and_resets_for_each_new_turn_after_restore() -> None:
    state = _game()
    resolve_effect(state, 2, "draw_cards", {"amount": 1})
    _permanent(state, "Narset, Parter of Veils", 1)
    before = len(state.players[2].hand)
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.draws_this_turn[2] == 1
    resolve_effect(restored, 2, "draw_cards", {"amount": 2})
    assert len(restored.players[2].hand) == before
    resolve_effect(restored, 1, "draw_cards", {"amount": 2})
    assert restored.draws_this_turn[1] == 2
    restored.step = Step.CLEANUP
    restored.cleanup_pending = False
    RulesEngine().next_step(restored)
    assert restored.draws_this_turn == {1: 0, 2: 0}
    resolve_effect(restored, 2, "draw_cards", {"amount": 2})
    assert len(restored.players[2].hand) == before + 1


def test_denied_draw_does_not_lose_to_empty_library_or_fire_draw_events() -> None:
    state = _game()
    _permanent(state, "Spirit of the Labyrinth", 2)
    resolve_effect(state, 1, "draw_cards", {"amount": 1})
    state.players[1].library.clear()
    resolve_effect(state, 1, "draw_cards", {"amount": 1})
    assert state.winner is None
    assert state.draws_this_turn[1] == 1


def test_dredge_replacement_does_not_consume_turn_draw_allowance() -> None:
    state = _game()
    _permanent(state, "Spirit of the Labyrinth", 2)
    dredger = canonical_card(
        'Stinkweed Imp', id="stinkweed", owner=1, controller=1,
        zone=Zone.GRAVEYARD,
    )
    state.cards[dredger.id] = dredger
    state.players[1].graveyard.append(dredger.id)
    resolve_effect(state, 1, "draw_cards", {"amount": 1})
    assert state.pending_mechanic_choice["kind"] == "draw"
    RulesEngine().take_action(state, 1, {"type": "choose_mechanic", "choice_id": dredger.id}, reject_invalid=True)
    assert state.draws_this_turn[1] == 0
    resolve_effect(state, 1, "draw_cards", {"amount": 2})
    assert state.draws_this_turn[1] == 1
