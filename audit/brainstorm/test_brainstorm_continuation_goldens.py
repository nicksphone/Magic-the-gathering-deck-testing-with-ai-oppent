"""Actual ordered/private/replacement episodes; direct helper probes labeled."""
import pytest
from ai.agent import AIAgent
from ai.information import decision_view, is_unknown
from effects.handlers import put_hand_on_library
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import ActionRejected
from test_brainstorm_desired import (position, add, act, cold, cast, advance,
                                     brainstorm, RULES)

@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('reverse', [False, True])
def test_explicit_topmost_first_order_survives_restore(seat, reverse):
    state = position(seat)
    state, source = brainstorm(state, seat)
    chosen = state.players[seat].hand[:2]
    if reverse:
        chosen = list(reversed(chosen))
    old_refs = {cid: state.cards[cid].zone_change_sequence for cid in chosen}
    move = RULES.legal_moves(state, seat)[0]
    assert move['kind'] == 'hand_top_order' and 'topmost first' in move['label']
    state = act(cold(state), seat, {'type': 'choose_mechanic', 'card_ids': chosen})
    state = cold(state)
    assert state.players[seat].library[-2:] == list(reversed(chosen))
    assert all(state.cards[cid].zone == Zone.LIBRARY and
               state.cards[cid].zone_change_sequence == old_refs[cid] + 1 for cid in chosen)
    assert state.cards[source].zone == Zone.GRAVEYARD

@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['duplicate', 'short', 'foreign', 'wrong-seat'])
def test_invalid_pending_selection_full_root_atomic(seat, bad):
    state = position(seat)
    other = add(state, 'Counterspell', 3-seat, Zone.HAND)
    state, _ = brainstorm(state, seat)
    ids = state.players[seat].hand[:2]
    if bad == 'duplicate': ids = [ids[0], ids[0]]
    if bad == 'short': ids = ids[:1]
    if bad == 'foreign': ids = [ids[0], other]
    actor = 3-seat if bad == 'wrong-seat' else seat
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        act(state, actor, {'type': 'choose_mechanic', 'card_ids': ids})
    assert serialize_match_snapshot(state) == before

@pytest.mark.parametrize('seat', [1, 2])
def test_pending_hand_options_private_and_returned_library_opaque(seat):
    state = position(seat)
    state, _ = brainstorm(state, seat)
    hand = list(state.players[seat].hand)
    before = serialize_match_snapshot(state)
    assert RULES.legal_moves(state, 3-seat) == []
    opponent, _ = decision_view(state, 3-seat, [])
    assert all(is_unknown(opponent.cards[cid]) for cid in hand)
    assert serialize_match_snapshot(state) == before
    selected = hand[:2]
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': selected})
    opponent, _ = decision_view(cold(state), 3-seat, [])
    assert all(is_unknown(opponent.cards[cid]) for cid in selected)

@pytest.mark.parametrize('seat', [1, 2])
def test_existing_ai_materializes_legal_private_order(seat):
    state = position(seat)
    state, _ = brainstorm(state, seat)
    moves = RULES.legal_moves(state, seat)
    private, private_moves = decision_view(state, seat, moves)
    before = serialize_match_snapshot(state)
    decision = AIAgent().choose_action(private, private_moves, seat)
    assert len(decision.action['card_ids']) == 2
    assert serialize_match_snapshot(state) == before
    state = act(state, seat, decision.action)
    assert not state.pending_mechanic_choice

@pytest.mark.parametrize('seat', [1, 2])
def test_direct_helper_short_hand_as_much_as_possible_protocol(seat):
    # Protocol-only amount/short-hand seam; not a fabricated canonical spell.
    state = position(seat)
    card = add(state, 'Counterspell', seat, Zone.HAND)
    put_hand_on_library(state, seat, {'amount': 2})
    assert state.pending_mechanic_choice['count'] == 1
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': [card]})
    assert state.players[seat].library[-1] == card
    assert not state.players[seat].hand

@pytest.mark.parametrize('seat', [1, 2])
def test_actual_dredge_pause_then_remaining_draws_then_put(seat):
    state = position(seat)
    imp = add(state, 'Stinkweed Imp', seat, Zone.GRAVEYARD)
    source = add(state, 'Brainstorm', seat, Zone.HAND)
    original_library = list(state.players[seat].library)
    state, _ = cast(state, seat, source, {'U': 1})
    state = advance(state, lambda s: bool(s.pending_mechanic_choice))
    assert state.pending_mechanic_choice['kind'] == 'draw'
    assert imp in state.pending_mechanic_choice['options']
    state = act(cold(state), seat, {'type': 'choose_mechanic', 'choice_id': imp})
    for _ in range(3):
        if state.pending_mechanic_choice['kind'] == 'hand_top_order': break
        assert state.pending_mechanic_choice['kind'] == 'draw'
        state = act(cold(state), seat, {'type': 'choose_mechanic', 'choice_id': 'draw'})
    assert state.pending_mechanic_choice['kind'] == 'hand_top_order'
    assert len(state.players[seat].library) == len(original_library) - 7
    assert imp in state.players[seat].hand and len(state.players[seat].hand) == 3
    other = next(cid for cid in state.players[seat].hand if cid != imp)
    state = act(cold(state), seat, {'type': 'choose_mechanic', 'card_ids': [imp, other]})
    assert state.players[seat].library[-1] == imp
    assert state.cards[source].zone == Zone.GRAVEYARD

@pytest.mark.parametrize('seat', [1, 2])
def test_actual_draw_replacement_six_draws_then_exactly_two_put(seat):
    state = position(seat)
    reflection = add(state, 'Thought Reflection', seat, Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, reflection)
    source = add(state, 'Brainstorm', seat, Zone.HAND)
    before = len(state.players[seat].library)
    state, _ = cast(state, seat, source, {'U': 1})
    state = advance(state, lambda s: bool(s.pending_mechanic_choice))
    assert state.pending_mechanic_choice['kind'] == 'hand_top_order'
    assert len(state.players[seat].hand) == 6
    assert len(state.players[seat].library) == before - 6
    selected = state.players[seat].hand[-2:]
    state = act(cold(state), seat, {'type': 'choose_mechanic', 'card_ids': selected})
    assert len(state.players[seat].hand) == 4
    assert state.players[seat].library[-2:] == list(reversed(selected))
    assert state.cards[source].zone == Zone.GRAVEYARD

@pytest.mark.parametrize('seat', [1, 2])
def test_whole_public_choice_intent_preserves_explicit_order(seat):
    from training.environment import TrainingEnvironment, decode_action
    state = position(seat)
    state, _ = brainstorm(state, seat)
    env = TrainingEnvironment()
    env._state = state
    public = RULES.legal_moves(state, seat)[0]
    assert 'effect_payload' not in public and 'resolving_item' not in public
    selected = list(reversed(state.players[seat].hand[:2]))
    before = serialize_match_snapshot(state)
    accepted = env.lookup_intent({**public, 'card_ids': selected}, seat=seat)
    assert decode_action(accepted['id']) == {'type': 'choose_mechanic', 'card_ids': selected}
    assert serialize_match_snapshot(state) == before
