"""Canonical original spells choose beneficiaries, not hostile default targets."""
import pytest
import json
from pathlib import Path

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.continuous import effective_combat_stats
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_ai_recurring_engines import add
from tests.test_landfall_alternatives import position


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['groundswell', 'rest-for-the-weary'])
@pytest.mark.parametrize('enhanced', [False, True])
@pytest.mark.parametrize('style', ['Aggro', 'Control', 'Tempo', 'Midrange'])
def test_original_alternative_targets_own_beneficiary_and_resolves(seat, name, enhanced, style):
    state, spell, own, _ = position(name, seat)
    enemy = add(state, 'Torrential Gearhulk', 3-seat)
    state.land_entries_this_turn[seat] = int(enhanced)
    move = next(m for m in RulesEngine().legal_moves(state, seat)
                if m['type'] == 'cast_spell' and m['card_id'] == spell.id)
    before = serialize_match_snapshot(state)
    action = AIAgent(archetype=style)._materialize_action(state, move, seat)
    assert serialize_match_snapshot(state) == before
    if name == 'groundswell':
        assert action['targets']['target_card_id'] == own.id
    else:
        assert action['targets']['target_player'] == seat
    state = checked_action(state, RulesEngine(), seat, action)
    assert resolve_top_of_stack(state)
    if name == 'groundswell':
        amount = 4 if enhanced else 2
        assert effective_combat_stats(state, own.id) == (5+amount, 6+amount)
        assert effective_combat_stats(state, enemy.id) == (5, 6)
    else:
        assert state.players[seat].life == (28 if enhanced else 24)
        assert state.players[3-seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['groundswell', 'rest-for-the-weary'])
def test_common_beneficial_polarity_does_not_guess_unknown_history(seat, name):
    state, spell, own, _ = position(name, seat)
    add(state, 'Torrential Gearhulk', 3-seat)
    state.land_entry_history_known = False
    move = next(m for m in RulesEngine().legal_moves(state, seat)
                if m['type'] == 'cast_spell' and m['card_id'] == spell.id)
    before = serialize_match_snapshot(state)
    action = AIAgent()._materialize_action(state, move, seat)
    assert action['targets'].get('target_card_id') == own.id if name == 'groundswell' else action['targets'].get('target_player') == seat
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['lightning-helix', 'essence-drain'])
@pytest.mark.parametrize('style', ['Aggro', 'Control', 'Tempo', 'Midrange'])
def test_damage_target_is_not_beneficiary_of_caster_life_gain(seat, name, style):
    from game_state.state import Zone
    from tests.test_ai_search_prefix import bare_state
    from tests.test_linked_damage_targets import raw_card
    state = bare_state(seat)
    raw = json.loads((Path(__file__).parent / 'fixtures/beneficiary_roles' / (name+'.json')).read_text())
    spell = raw_card(state, raw, seat, Zone.HAND)
    state.players[seat].mana_pool = {color: 5 for color in 'WUBRGC'}
    move = next(m for m in RulesEngine().legal_moves(state, seat)
                if m['type'] == 'cast_spell' and m['card_id'] == spell.id)
    before = serialize_match_snapshot(state)
    action = AIAgent(archetype=style)._materialize_action(state, move, seat)
    assert serialize_match_snapshot(state) == before
    assert action['targets']['target_player'] == 3-seat
    state = checked_action(state, RulesEngine(), seat, action)
    assert resolve_top_of_stack(state)
    assert state.players[3-seat].life == 17
    assert state.players[seat].life == 23


def damage_gain_position(seat, name):
    from game_state.state import Zone
    from tests.test_ai_search_prefix import bare_state
    from tests.test_linked_damage_targets import raw_card
    state = bare_state(seat)
    raw = json.loads((Path(__file__).parent / 'fixtures/beneficiary_roles' / (name+'.json')).read_text())
    spell = raw_card(state, raw, seat, Zone.HAND)
    state.players[seat].mana_pool = {color: 5 for color in 'WUBRGC'}
    return state, spell


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['lightning-helix', 'essence-drain'])
@pytest.mark.parametrize('case', ['self_at_three', 'damage_prevented', 'illegal_creature'])
def test_complete_damage_gain_instruction_resolves_or_fizzles_as_a_whole(seat, name, case):
    from effects.registry import resolve_effect
    state, spell = damage_gain_position(seat, name)
    targets = {'target_player': 3-seat}
    if case == 'self_at_three':
        state.players[seat].life = 3
        targets = {'target_player': seat}
    elif case == 'damage_prevented':
        from rules_engine.prevention import add_player_prevention_shield
        add_player_prevention_shield(state, 3-seat, 3)
    else:
        recipient = add(state, 'Torrential Gearhulk', 3-seat)
        targets = {'target_card_id': recipient.id}
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': spell.id, 'targets': targets})
    if case == 'illegal_creature':
        resolve_effect(state, seat, 'exile', {'target_card_id': recipient.id})
    from game_state.serializers import deserialize_match_snapshot
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(state)
    assert state.winner is None
    assert state.players[seat].life == (3 if case == 'self_at_three' else 20 if case == 'illegal_creature' else 23)
    assert state.players[3-seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['lightning-helix', 'essence-drain'])
def test_paid_copy_changes_damage_target_not_untargeted_caster_gain(seat, name):
    from game_state.state import Zone
    from tests.test_linked_damage_targets import raw_card
    from tests.test_real_ordered_spell_copy import pass_twice
    from game_state.serializers import deserialize_match_snapshot
    state, spell = damage_gain_position(seat, name)
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': spell.id,
                            'targets': {'target_player': 3-seat}})
    original = state.stack[-1].id
    raw = json.loads((Path(__file__).parent / 'fixtures/coupled_targets/twincast.json').read_text())
    copier = 3-seat
    twincast = raw_card(state, raw, copier, Zone.HAND)
    state.players[copier].mana_pool = {'U': 2}
    state = checked_action(state, RulesEngine(), seat, {'type': 'pass_priority'})
    state = checked_action(state, RulesEngine(), copier,
                           {'type': 'cast_spell', 'card_id': twincast.id,
                            'targets': {'target_stack_id': original}})
    state = pass_twice(state)
    assert state.pending_mechanic_choice['kind'] == 'copy_target'
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), copier,
                           {'type': 'choose_mechanic', 'card_ids': [f'target_player:{seat}']})
    assert resolve_top_of_stack(state)
    assert state.players[seat].life == 17
    assert state.players[copier].life == 23
    assert state.stack[-1].id == original
    assert state.stack[-1].payload['__announced_targets']['target_player'] == copier
