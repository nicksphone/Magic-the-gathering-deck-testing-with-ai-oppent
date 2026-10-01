"""Real card faces and explicit return packets; not full Jace ability support."""
import json
from pathlib import Path

import pytest

from effects.registry import resolve_effect
from game_state.state import CardInstance, Zone, assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.card_faces import select_cast_face
from rules_engine.continuous import effective_combat_stats
from rules_engine.state_based_actions import apply_state_based_actions
from tests.test_counter_replacements import source as modifier, choose
from tests.test_counter_prohibitions import source as permanent
from tests.test_restricted_mana import clean

ROWS = json.loads((Path(__file__).parent / 'fixtures/transformed_entry.json').read_text())
ROW = ROWS[0]


def jace(state, player=1, row=ROW):
    card = CardInstance(state.allocate_object_id(), row['name'], player, player, Zone.BATTLEFIELD,
                        layout=row['layout'], card_faces=row['card_faces'])
    face = select_cast_face(card, 0)
    state.cards[face.id] = face
    state.players[player].battlefield.append(face.id)
    assign_static_order_on_battlefield_entry(state, face.id)
    return face


@pytest.mark.parametrize('first,expected', [('add', 12), ('double', 11)])
@pytest.mark.parametrize('controller', [1, 2])
def test_back_face_entry_loyalty_choices_preserve_exiled_front_and_resume(first, expected, controller):
    state = clean(controller)
    card = jace(state)
    modifier(state, 'Doubling Season', controller)
    modifier(state, "Lae'zel, Vlaakith's Champion", controller)
    resolve_effect(state, controller, 'exile_return_transformed', {'target_card_id': card.id})
    assert card.zone == Zone.EXILE and card.selected_face_index == 0
    assert card.name == ROW['card_faces'][0]['name'] and card.loyalty is None
    assert card.id in state.players[1].exile and card.id not in state.players[controller].battlefield
    assert state.pending_replacement_choice['player_id'] == controller
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = choose(state, first, controller)
    card = state.cards[card.id]
    assert card.selected_face_index == 1 and card.loyalty == expected
    assert card.name == ROW['card_faces'][1]['name'] and card.types == ['Planeswalker']
    assert card.zone == Zone.BATTLEFIELD and card.controller == controller and card.owner == 1
    assert state.players[controller].battlefield.count(card.id) == 1
    assert card.id not in state.players[1].exile
    assert sum('is exiled.' in line for line in state.log) == 1


def test_noncast_back_face_does_not_inherit_source_x_escape_or_life_choices():
    state = clean()
    card = jace(state)
    resolve_effect(state, 1, 'exile_return_transformed', {
        'target_card_id': card.id, 'x_value': 42, '__escaped': True, '__phyrexian_life_symbols': 3,
    })
    assert card.loyalty == 5 and not card.counters
    assert card.zone == Zone.BATTLEFIELD and card.selected_face_index == 1


def test_transformed_entry_uses_counter_types_of_back_face_not_front():
    state = clean()
    card = jace(state)
    permanent(state, 'Solemnity')
    resolve_effect(state, 1, 'exile_return_transformed', {'target_card_id': card.id})
    assert card.loyalty == 5


def test_later_zone_exit_restores_real_front_characteristics_not_entry_loyalty():
    state = clean()
    card = jace(state)
    modifier(state, 'Doubling Season')
    resolve_effect(state, 1, 'exile_return_transformed', {'target_card_id': card.id})
    assert card.loyalty == 10
    resolve_effect(state, 1, 'return_permanent_to_hand', {'target_card_id': card.id})
    apply_state_based_actions(state)
    assert card.selected_face_index == 0 and card.loyalty is None
    assert card.types == ['Creature'] and (card.power, card.toughness) == (0, 2)


def test_in_place_transform_preserves_counters_and_uses_printed_loyalty_for_restore():
    state = clean()
    card = jace(state)
    card.counters['+1/+1'] = 3
    resolve_effect(state, 1, 'transform_card', {'target_card_id': card.id, 'face_index': 1})
    assert card.counters['+1/+1'] == 3 and card.loyalty == 0
    resolve_effect(state, 1, 'transform_card', {'target_card_id': card.id, 'face_index': 0})
    assert card.counters['+1/+1'] == 3
    assert effective_combat_stats(state, card.id) == (3, 5)


def test_loyalty_counters_survive_planeswalker_creature_face_changes():
    from rules_engine.counter_placement import put_counters
    state = clean()
    card = jace(state)
    put_counters(state, 'loyalty', 3, target_card_id=card.id)
    resolve_effect(state, 1, 'transform_card', {'target_card_id': card.id, 'face_index': 1})
    assert card.loyalty == 3 and 'loyalty' not in card.counters
    resolve_effect(state, 1, 'transform_card', {'target_card_id': card.id, 'face_index': 0})
    assert card.loyalty is None and card.counters['loyalty'] == 3
    resolve_effect(state, 1, 'transform_card', {'target_card_id': card.id, 'face_index': 1})
    assert card.loyalty == 3 and 'loyalty' not in card.counters


def test_planeswalker_to_planeswalker_transform_preserves_current_loyalty():
    state = clean()
    card = jace(state, row=ROWS[1])
    card.loyalty = 7
    resolve_effect(state, 1, 'transform_card', {'target_card_id': card.id, 'face_index': 1})
    assert card.loyalty == 7 and card.name == ROWS[1]['card_faces'][1]['name']
    resolve_effect(state, 1, 'transform_card', {'target_card_id': card.id, 'face_index': 0})
    assert card.loyalty == 7


def test_back_face_without_printed_loyalty_enters_at_zero_and_dies_to_sba():
    state = clean()
    card = jace(state, row=ROWS[2])
    resolve_effect(state, 1, 'exile_return_transformed', {'target_card_id': card.id})
    assert card.selected_face_index == 1 and card.loyalty == 0
    assert card.zone == Zone.BATTLEFIELD
    apply_state_based_actions(state)
    assert card.zone == Zone.GRAVEYARD and card.id in state.players[1].graveyard


def test_in_place_transform_to_face_without_printed_loyalty_keeps_existing_counters():
    state = clean()
    card = jace(state, row=ROWS[2])
    card.loyalty = 2
    resolve_effect(state, 1, 'transform_card', {'target_card_id': card.id, 'face_index': 1})
    apply_state_based_actions(state)
    assert card.zone == Zone.BATTLEFIELD and card.loyalty == 2
