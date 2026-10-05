"""One canonical permanent in both target roles: constructed continuous layers."""
import json
from pathlib import Path
import pytest

from effects import handlers
from effects.registry import resolve_effect
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.type_effects import add_type_effect, clear_type_effects
from tests.test_linked_damage_targets import position, raw_card
from game_state.state import Zone


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('enhanced', [False, True])
def test_two_legal_instances_damage_same_object_as_one_event(seat, enhanced, monkeypatch):
    state, spell, _, walker, _ = position(seat, 'planeswalker')
    # Construct an animation layer, not a claimed implementation of an animation card.
    add_type_effect(state, walker.id, ['Creature'])
    resolve_effect(state, seat, 'set_base_stats', {'target_card_id': walker.id, 'base_power': 10, 'base_toughness': 10})
    state.land_entries_this_turn[seat] = int(enhanced)
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': spell.id,
                            'targets': {'target_card_ids': [walker.id, walker.id]}})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    observed = []
    original = handlers.emit_event
    def capture(state, event, payload):
        if event == 'damage_dealt' and payload.get('target_card_id') == walker.id:
            observed.append(dict(payload))
        return original(state, event, payload)
    monkeypatch.setattr(handlers, 'emit_event', capture)
    assert resolve_top_of_stack(state)
    expected = 6 if enhanced else 2
    assert state.cards[walker.id].loyalty == 7-expected
    assert state.cards[walker.id].counters['__damage_marked'] == expected
    assert len(observed) == 1
    assert observed[0]['amount'] == expected


@pytest.mark.parametrize('seat', [1, 2])
def test_same_object_losing_creature_type_only_takes_planeswalker_instance(seat):
    state, spell, _, walker, _ = position(seat, 'planeswalker')
    add_type_effect(state, walker.id, ['Creature'])
    resolve_effect(state, seat, 'set_base_stats', {'target_card_id': walker.id, 'base_power': 10, 'base_toughness': 10})
    state.land_entries_this_turn[seat] = 1
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': spell.id,
                            'targets': {'target_card_ids': [walker.id, walker.id]}})
    clear_type_effects(state.cards[walker.id])
    assert resolve_top_of_stack(state)
    assert state.cards[walker.id].loyalty == 4
    assert state.cards[walker.id].counters.get('__damage_marked', 0) == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('tagged', [False, True])
def test_same_source_batch_player_damage_applies_canonical_armor_once(seat, tagged):
    state, spell, _, _, _ = position(seat)
    raw = json.loads((Path(__file__).parent / 'fixtures/linked_damage/urzas-armor.json').read_text())
    raw_card(state, raw, 3-seat, Zone.BATTLEFIELD)
    tags = {'__batch_damage': True} if tagged else {}
    resolve_effect(state, seat, 'deal_damage_batch', {
        '__source_card_id': spell.id,
        'recipients': [{'target_player': 3-seat, 'amount': 3, **tags}, {'target_player': 3-seat, 'amount': 3, **tags}],
    })
    assert state.players[3-seat].life == 15


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('armor_first', [False, True])
def test_combined_damage_replacement_order_and_resume_uses_one_event(seat, armor_first):
    state, spell, _, _, _ = position(seat)
    folder = Path(__file__).parent / 'fixtures/linked_damage'
    armor = raw_card(state, json.loads((folder/'urzas-armor.json').read_text()), 3-seat, Zone.BATTLEFIELD)
    furnace = raw_card(state, json.loads((folder/'furnace-of-rath.json').read_text()), seat, Zone.BATTLEFIELD)
    state.replacement_choice_required = True
    state.replacement_choice_players = {3-seat}
    resolve_effect(state, seat, 'deal_damage_batch', {
        '__source_card_id': spell.id,
        'recipients': [{'target_player': 3-seat, 'amount': 3}, {'target_player': 3-seat, 'amount': 3}],
    })
    assert state.pending_replacement_choice['amount'] == 6
    first = armor.id if armor_first else furnace.id
    for index in range(3):
        if state.pending_replacement_choice is None:
            break
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
        pending = state.pending_replacement_choice
        selected = first if index == 0 else pending['options'][0]['source_id']
        state = checked_action(state, RulesEngine(), 3-seat,
                               {'type': 'choose_replacement', 'replacement_source_id': selected})
    assert state.pending_replacement_choice is None
    assert state.players[3-seat].life == (10 if armor_first else 9)
