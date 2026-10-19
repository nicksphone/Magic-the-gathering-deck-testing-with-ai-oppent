"""Independent canonical handler slice, NOT paid-spell/compiler qualification."""
from copy import deepcopy

import pytest

from api_contracts import MechanicChoice
from effects.handlers import put_land_from_hand
from game_state.serializers import deserialize_match_snapshot, serialize_match, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.keyword_actions import finish_mechanic_choice
from tests.test_optional_land_from_hand_audit import roundtrip, setup


def pending(seat, *, tapped=False, optional=True, shock=False):
    state, _, land, _ = setup('Growth Spiral', seat, shock=shock)
    # Unit entrypoint only: this deliberately does not inject a spell/StackItem
    # and cannot stand in for the unchanged paid-path audit.
    put_land_from_hand(state, seat, {'optional': optional, 'tapped': tapped})
    assert state.pending_mechanic_choice['kind'] == 'land_from_hand'
    assert land.id in state.players[seat].hand
    return state, land


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('tapped', [False, True])
def test_real_selected_identity_zone_history_and_private_pending(seat, tapped, tmp_path):
    state, land = pending(seat, tapped=tapped)
    before = serialize_match_snapshot(state)
    public = serialize_match(state)
    other = serialize_match(state, look_players=(3-seat,))
    for body in [public, other]:
        assert set(body['pending_mechanic_choice']) == {'kind', 'player_id', 'label', 'count', 'min_count'}
    assert not RulesEngine().legal_moves(state, 3-seat)
    offered = RulesEngine().legal_moves(state, seat)[0]
    assert offered['options'] == [land.id] and offered['min_count'] == 0
    state = roundtrip(state, tmp_path / 'slice-only-local.sqlite')
    chosen = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': [land.id]})
    assert serialize_match_snapshot(state) == before
    assert land.id not in chosen.players[seat].hand
    assert land.id in chosen.players[seat].battlefield
    assert chosen.cards[land.id].zone_change_sequence == before['cards'][land.id]['zone_change_sequence'] + 1
    assert chosen.cards[land.id].tapped is tapped
    assert chosen.players[seat].lands_played_this_turn == 1
    assert chosen.players[seat].land_plays_recorded_on_turn == 1
    assert chosen.land_entries_this_turn[seat] == 1
    assert chosen.pending_mechanic_choice is None
    with pytest.raises(ActionRejected):
        checked_action(chosen, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': [land.id]})


@pytest.mark.parametrize('seat', [1, 2])
def test_existing_typed_decline_helper_continuation_without_public_validator_claim(seat):
    state, land = pending(seat)
    model = MechanicChoice(type='choose_mechanic', card_ids=[])
    assert model.card_ids == []
    assert finish_mechanic_choice(state, seat, {'type': 'choose_mechanic', 'card_ids': []})
    assert land.id in state.players[seat].hand
    assert state.pending_mechanic_choice is None
    assert state.players[seat].lands_played_this_turn == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_public_checked_decline_requires_one_kind_validation_hook_desired(seat):
    state, land = pending(seat)
    chosen = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': []})
    assert chosen.pending_mechanic_choice is None
    assert land.id in chosen.players[seat].hand


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['wrong_seat', 'nonland', 'duplicate', 'missing', 'foreign', 'left_returned'])
def test_invalid_and_stale_actual_choices_do_not_mutate_root(seat, bad):
    state, land = pending(seat)
    actor = seat
    ids = [land.id]
    if bad == 'wrong_seat':
        actor = 3-seat
    elif bad == 'nonland':
        ids = [next(cid for cid in state.players[seat].hand if 'Land' not in state.cards[cid].types)]
    elif bad == 'duplicate':
        ids *= 2
    elif bad == 'missing':
        ids = ['not-an-offered-object']
    elif bad == 'foreign':
        ids = state.players[3-seat].hand[:1]
    else:
        # Explicit stale-request unit mutation, not a historical game claim.
        state.cards[land.id].move_to_zone(Zone.EXILE)
        state.cards[land.id].move_to_zone(Zone.HAND)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), actor, {'type': 'choose_mechanic', 'card_ids': ids})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('tapped', [False, True])
def test_existing_shock_pause_carries_queue_once_and_no_hand_options(seat, tapped, tmp_path):
    state, land = pending(seat, tapped=tapped, shock=True)
    # Synthetic framework unit continuation, not asserted to be this card's
    # Oracle: prove transfer through the existing secondary entry pause once.
    state.pending_mechanic_choice['continuation_effects'] = [
        {'effect_key': 'draw_cards', 'payload': {'amount': 1}},
    ]
    expected_hand = len(state.players[seat].hand)
    state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': [land.id]})
    assert state.pending_mechanic_choice['kind'] == 'land_entry'
    assert 'land_references' not in state.pending_mechanic_choice
    assert len(state.players[seat].hand) == expected_hand
    state = roundtrip(state, tmp_path / 'entry-only-local.sqlite')
    result = checked_action(state, RulesEngine(), seat,
                            {'type': 'choose_mechanic', 'choice_id': 'pay_two_life'})
    assert result.players[seat].life == 18
    assert result.cards[land.id].tapped is tapped
    assert result.pending_mechanic_choice is None
    assert len(result.players[seat].hand) == expected_hand
    assert result.draws_this_turn[seat] == 1
    assert result.land_entries_this_turn[seat] == 1
    assert result.players[seat].lands_played_this_turn == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_no_invalid_explicit_identity_fallback_and_mandatory_no_decline(seat):
    state, land = pending(seat, optional=False)
    before = serialize_match_snapshot(state)
    assert not finish_mechanic_choice(state, seat, {'type': 'choose_mechanic', 'card_ids': []})
    assert serialize_match_snapshot(state) == before
    state.pending_mechanic_choice = None
    put_land_from_hand(state, seat, {'land_id': 'unavailable-identity', 'optional': True})
    assert land.id in state.players[seat].hand and state.pending_mechanic_choice is None


@pytest.mark.parametrize('seat', [1, 2])
def test_no_eligible_current_hand_does_not_open_empty_choice(seat):
    state, _, _, _ = setup('Growth Spiral', seat, eligible=False)
    put_land_from_hand(state, seat, {'optional': True})
    assert state.pending_mechanic_choice is None
    assert state.players[seat].lands_played_this_turn == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_multiple_candidates_remain_explicit_and_unselected_private(seat):
    from tests.ai_knowledge_consumer_fixture import take
    state, _, chosen, _ = setup('Growth Spiral', seat, shock=True)
    other = take(state, 'Forest', seat, Zone.HAND)
    put_land_from_hand(state, seat, {'optional': True, 'tapped': False})
    offered = RulesEngine().legal_moves(state, seat)[0]
    assert set(offered['options']) == {chosen.id, other.id}
    assert chosen.id in state.players[seat].hand and other.id in state.players[seat].hand
    state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': [chosen.id]})
    assert state.pending_mechanic_choice['kind'] == 'land_entry'
    public_entry = serialize_match(state)['pending_mechanic_choice']
    assert other.id not in str(public_entry)
    state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'choice_id': 'tapped'})
    assert chosen.id in state.players[seat].battlefield and other.id in state.players[seat].hand


@pytest.mark.parametrize('seat', [1, 2])
def test_handler_candidates_are_collected_after_real_draw(seat):
    from effects.handlers import draw_cards
    state, _, _, drawn = setup('Growth Spiral', seat, eligible=False, drawn_land=True)
    draw_cards(state, seat, {'amount': 1})
    assert drawn in state.players[seat].hand
    put_land_from_hand(state, seat, {'optional': True, 'tapped': False})
    assert RulesEngine().legal_moves(state, seat)[0]['options'] == [drawn]
    state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': [drawn]})
    assert drawn in state.players[seat].battlefield
    assert state.players[seat].lands_played_this_turn == 1
