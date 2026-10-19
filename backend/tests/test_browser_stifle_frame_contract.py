"""Browser counter fixtures must announce kinds without weakening native targets."""
import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.targeting import stack_object_kind
from tests.modal_contract_support import canonical_fixture
from tests.test_counterability_scope import add_card, state_with_card


def test_browser_stifle_fixture_is_offered_and_counters_only_the_ability():
    state = canonical_fixture('stifle_protection')
    shepherd = next(card for card in state.cards.values() if card.name == 'Allosaurus Shepherd')
    stifle = next(card for card in state.cards.values() if card.name == 'Stifle')
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    move = next(move for move in RulesEngine().legal_moves(state, 1)
                if move.get('card_id') == stifle.id and move['type'] == 'cast_spell')
    assert [target['id'] for target in move['target_hints']['stack_targets']] == ['target']
    state = checked_action(state, RulesEngine(), 1, {
        'type': 'cast_spell', 'card_id': stifle.id,
        'targets': {'target_stack_id': 'target'},
    })
    assert len(state.stack) == 2
    assert resolve_top_of_stack(state)
    assert not state.stack
    assert state.cards[shepherd.id].zone == Zone.BATTLEFIELD
    assert state.players[2].battlefield.count(shepherd.id) == 1
    assert state.cards[stifle.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_declared_ability_is_stifle_target_for_either_seat(seat):
    state, shepherd = state_with_card('Allosaurus Shepherd', Zone.BATTLEFIELD, controller=3 - seat)
    state.priority_player = seat
    stifle = add_card(state, 'Stifle', Zone.HAND, seat)
    state.players[seat].mana_pool['U'] = 1
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'cast_spell', 'card_id': stifle.id,
        'targets': {'target_stack_id': 'target'},
    })
    assert resolve_top_of_stack(state)
    assert not state.stack
    assert state.cards[shepherd.id].zone == Zone.BATTLEFIELD
    assert state.players[3 - seat].battlefield.count(shepherd.id) == 1


@pytest.mark.parametrize('origin,kind', [(Zone.STACK, 'spell'), (Zone.BATTLEFIELD, 'activated')])
@pytest.mark.parametrize('seat', [1, 2])
def test_declared_kind_survives_source_departure_and_snapshot(origin, kind, seat):
    state, source = state_with_card('Allosaurus Shepherd', origin, controller=seat)
    if origin == Zone.BATTLEFIELD:
        state.players[seat].battlefield.remove(source.id)
    source.move_to_zone(Zone.GRAVEYARD)
    state.players[seat].graveyard.append(source.id)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert state.cards[source.id].zone == Zone.GRAVEYARD
    assert stack_object_kind(state, state.stack[0]) == kind


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('declared_kind', [None, 'spell'])
def test_stifle_does_not_offer_or_accept_unknown_frames_or_spells(seat, declared_kind):
    state, _ = state_with_card('Allosaurus Shepherd', Zone.BATTLEFIELD, controller=3 - seat)
    state.priority_player = seat
    state.stack[0].payload = {} if declared_kind is None else {'__announced_stack_kind': declared_kind}
    stifle = add_card(state, 'Stifle', Zone.HAND, seat)
    state.players[seat].mana_pool['U'] = 1
    before = serialize_match_snapshot(state)
    assert not any(move.get('card_id') == stifle.id
                   for move in RulesEngine().legal_moves(state, seat))
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {
            'type': 'cast_spell', 'card_id': stifle.id,
            'targets': {'target_stack_id': 'target'},
        })
    assert serialize_match_snapshot(state) == before
