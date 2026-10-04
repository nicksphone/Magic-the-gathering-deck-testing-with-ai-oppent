from copy import deepcopy
from unittest.mock import patch

import pytest

from ai.information import decision_view
from ai.agent import AIAgent
from effects.registry import resolve_effect
from game_state.observations import observe_cards
from game_state.serializers import serialize_match, serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import Zone, draw_card
from rules_engine.engine import RulesEngine
from rules_engine.action_validation import checked_action
from tests.test_ai_information_boundary import counter_position
from tests.test_ai_recurring_engines import add
from tests.test_surveil_mill import add as add_card


@pytest.mark.parametrize('seat', [1, 2])
def test_real_reveal_remembers_whole_hand_including_excluded_lands_after_restart(seat):
    state, bolt, hidden = counter_position(seat)
    other = 3-seat
    land = add_card(state, 'Island', other, Zone.HAND)
    discarded = add(state, 'Grizzly Bears', other, Zone.HAND)
    state.mechanic_choice_players = {seat}
    resolve_effect(state, seat, 'choose_revealed_discard',
                   {'target_player': other, 'excluded_types': ['Land']})
    assert hidden.id in state.pending_mechanic_choice['options']
    assert land.id not in state.pending_mechanic_choice['options']
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'choose_mechanic', 'card_ids': [discarded.id]})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': bolt.id,
                                                      'targets': {'target_player': other}})
    state = checked_action(state, RulesEngine(), seat, {'type': 'pass_priority'})
    before = serialize_match_snapshot(state)
    view, _ = decision_view(state, seat, [])
    assert view.cards[hidden.id].name == 'Counterspell'
    assert view.cards[land.id].name == 'Island'
    assert any(move['type'] == 'cast_spell' and move['card_id'] == hidden.id
               for move in RulesEngine().legal_moves(view, other))
    assert serialize_match_snapshot(state) == before
    assert 'card_observations' not in serialize_match(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('origin', [Zone.BATTLEFIELD, Zone.GRAVEYARD])
def test_actual_public_return_remembers_identity_without_reading_new_hidden_metadata(seat, origin):
    state, _, _ = counter_position(seat)
    other = 3-seat
    bear = add(state, 'Grizzly Bears', other, origin)
    effect = 'return_permanent_to_hand' if origin == Zone.BATTLEFIELD else 'return_from_graveyard'
    resolve_effect(state, other if origin == Zone.GRAVEYARD else seat, effect, {'target_card_id': bear.id})
    assert bear.zone == Zone.HAND
    before = deepcopy(state.card_observations)
    bear.private_note = {'secret': True}
    bear.oracle_text = 'This unobserved alteration is not part of remembered information.'
    view, _ = decision_view(state, seat, [])
    assert view.cards[bear.id].name == 'Grizzly Bears'
    assert view.cards[bear.id].oracle_text != bear.oracle_text
    assert not hasattr(view.cards[bear.id], 'private_note')
    assert state.card_observations == before


@pytest.mark.parametrize('seat', [1, 2])
def test_hidden_library_trip_and_draw_never_restore_physical_identity(seat):
    state, _, hidden = counter_position(seat)
    other = 3-seat
    observe_cards(state, [hidden.id])
    state.players[other].hand.remove(hidden.id)
    hidden.move_to_zone(Zone.LIBRARY)
    state.players[other].library.append(hidden.id)
    state.rng.shuffle(state.players[other].library)
    view, _ = decision_view(state, seat, [])
    assert view.cards[hidden.id].name == ''
    assert hidden.id not in view.card_observations[seat]
    state.players[other].library.remove(hidden.id)
    state.players[other].library.append(hidden.id)
    draw_card(state, other)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    view, _ = decision_view(state, seat, [])
    assert view.cards[hidden.id].name == ''
    assert hidden.id not in view.card_observations[seat]


@pytest.mark.parametrize('seat', [1, 2])
def test_private_observation_is_not_shared_and_new_unrevealed_draw_stays_unknown(seat):
    state, _, hidden = counter_position(seat)
    other = 3-seat
    observe_cards(state, [hidden.id], viewers=[other])
    view, _ = decision_view(state, seat, [])
    assert view.cards[hidden.id].name == ''
    assert view.card_observations == {seat: {}}
    observe_cards(state, [hidden.id], viewers=[seat])
    cid = state.players[other].library[-1]
    draw_card(state, other)
    view, _ = decision_view(state, seat, [])
    assert view.cards[hidden.id].name == 'Counterspell'
    assert view.cards[cid].name == ''


def test_legacy_memory_and_projected_reveals_remain_conservative():
    state, _, hidden = counter_position(1)
    payload = serialize_match_snapshot(state)
    payload.pop('card_observations')
    state = deserialize_match_snapshot(payload)
    assert state.card_observations == {}
    view, _ = decision_view(state, 1, [])
    observe_cards(view, [hidden.id])
    assert view.card_observations == {1: {}}
    assert view.cards[hidden.id].name == ''


@pytest.mark.parametrize('seat', [1, 2])
def test_face_down_exile_does_not_expose_stale_hand_records(seat):
    state, _, hidden = counter_position(seat)
    observe_cards(state, [hidden.id])
    state.players[hidden.owner].hand.remove(hidden.id)
    state.players[hidden.owner].exile.append(hidden.id)
    hidden.move_to_zone(Zone.EXILE)
    hidden.exile_face_down = True
    view, _ = decision_view(state, seat, [])
    assert view.cards[hidden.id].name == ''
    assert hidden.id not in view.card_observations[seat]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Control', 'Tempo', 'Ramp', 'Aggro', 'Tokens', 'Drain'])
def test_deeper_search_can_use_revealed_counter_but_not_unseen_counter(seat, style):
    state, bolt, counter = counter_position(seat)
    move = {'type': 'cast_spell', 'card_id': bolt.id, 'targets': {'target_player': 3-seat}}
    ai = AIAgent(archetype=style, difficulty='master')
    unseen, _ = decision_view(state, seat, [])
    with patch.object(ai, '_materialize_action', wraps=ai._materialize_action) as materialize:
        ai._strategic_line_score(unseen, move, seat, 3)
        assert not any(call.args[1].get('card_id') == counter.id for call in materialize.call_args_list)
    observe_cards(state, [counter.id])
    seen, _ = decision_view(state, seat, [])
    before = serialize_match_snapshot(seen)
    with patch.object(ai, '_materialize_action', wraps=ai._materialize_action) as materialize:
        ai._strategic_line_score(seen, move, seat, 3)
        assert any(call.args[1].get('card_id') == counter.id and call.args[2] == 3-seat
                   for call in materialize.call_args_list)
    assert serialize_match_snapshot(seen) == before
