"""Genuine paid opponent spells, not empty legacy stack rows, test Boon costs."""
import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import StackItem, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.targeting import stack_object_kind
from tests.test_life_total_lock import game
from tests.damage_life_printed_79 import canonical_card


def paid_position(seat, *, creature=True):
    state = game()
    opponent = 3 - seat
    font = canonical_card('Font of Agonies', id='font', owner=seat, controller=seat, zone=Zone.BATTLEFIELD)
    boon = canonical_card('Withering Boon', id='boon', owner=seat, controller=seat, zone=Zone.HAND)
    spell = (canonical_card('Grizzly Bears', id='bear', owner=opponent, controller=opponent, zone=Zone.HAND) if creature else
             canonical_card('Lightning Bolt', id='bolt', owner=opponent, controller=opponent, zone=Zone.HAND))
    state.cards.update({c.id: c for c in (font, boon, spell)})
    state.players[seat].battlefield.append(font.id)
    state.players[seat].hand.append(boon.id)
    state.players[opponent].hand.append(spell.id)
    state.players[seat].mana_pool.update({'B': 1, 'C': 1})
    state.players[opponent].mana_pool.update({'G': 1, 'C': 1} if creature else {'R': 1})
    state.active_player = state.priority_player = opponent
    action = {'type': 'cast_spell', 'card_id': spell.id}
    if not creature:
        action['targets'] = {'target_player': seat}
    state = checked_action(state, RulesEngine(), opponent, action)
    item = state.stack[-1]
    assert item.payload['mana_spent'] == (2 if creature else 1)
    assert stack_object_kind(state, item) == 'spell'
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.stack[-1].payload == item.payload
    assert stack_object_kind(restored, restored.stack[-1]) == 'spell'
    state = checked_action(restored, RulesEngine(), opponent, {'type': 'pass_priority'})
    assert state.priority_player == seat
    return state, spell.id, item.id


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_creature_counter_life_cost_font_and_snapshot_both_seats(seat):
    state, creature, item = paid_position(seat)
    move = next(m for m in RulesEngine().legal_moves(state, seat) if m.get('card_id') == 'boon')
    assert move['type'] == 'cast_spell'
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': 'boon',
                                      'targets': {'target_stack_id': item}})
    assert state.players[seat].life == 17
    assert [i.source_card_id for i in state.stack] == [creature, 'boon', 'font']
    assert resolve_top_of_stack(state) and state.cards['font'].counters.get('blood') == 3
    assert resolve_top_of_stack(state)
    assert creature in state.players[3-seat].graveyard and 'boon' in state.players[seat].graveyard
    assert not state.stack


def test_genuine_paid_noncreature_spell_remains_invalid_and_root_atomic():
    state, _, item = paid_position(1, creature=False)
    before = serialize_match_snapshot(state)
    assert not any(m.get('card_id') == 'boon' for m in RulesEngine().legal_moves(state, 1))
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {'type': 'cast_spell', 'card_id': 'boon',
                                               'targets': {'target_stack_id': item}})
    assert serialize_match_snapshot(state) == before


def test_empty_legacy_row_is_not_inferred_to_be_a_creature_spell():
    state, creature, _ = paid_position(1)
    state.stack = [StackItem('legacy-bear', creature, 2, 'Grizzly Bears', 'noop', {})]
    before = serialize_match_snapshot(state)
    assert stack_object_kind(state, state.stack[0]) == 'legacy_unknown'
    assert not any(m.get('card_id') == 'boon' for m in RulesEngine().legal_moves(state, 1))
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {'type': 'cast_spell', 'card_id': 'boon',
                                               'targets': {'target_stack_id': 'legacy-bear'}})
    assert serialize_match_snapshot(state) == before
