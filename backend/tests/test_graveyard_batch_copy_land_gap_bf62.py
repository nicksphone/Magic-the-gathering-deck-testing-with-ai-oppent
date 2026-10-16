"""Genuine producer admission, never a fabricated artifact shockland."""
import pytest

from game_state.state import Zone
from rules_engine.ability_model import build_ability_spec
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import extract_activated_abilities
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.type_effects import effective_types
from tests.graveyard_batch_boundary_support_bf62 import position, raw_card
from tests.graveyard_batch_native_support_bf62 import cast_vaults, choose, place, snapshot


@pytest.mark.parametrize('owner', [1, 2])
def test_genuine_coating_to_pool_then_returning_steel_must_admit_native_copy_payment(owner):
    names = ('Open the Vaults', 'Liquimetal Coating', 'Breeding Pool', 'Sculpting Steel')
    state = position(names, names, active=owner)
    coating = place(state, 'Liquimetal Coating', Zone.BATTLEFIELD, owner)
    pool = place(state, 'Breeding Pool', Zone.BATTLEFIELD, owner)
    steel = place(state, 'Sculpting Steel', Zone.GRAVEYARD, owner)
    assert state.cards[pool].type_line == raw_card('Breeding Pool')['type_line']
    assert 'Artifact' not in effective_types(state, pool)
    action = {'type': 'activate_ability', 'card_id': coating, 'ability_index': 0,
              'targets': {'target_card_id': pool}}
    ability = extract_activated_abilities(state.cards[coating])[0]
    assert ability['mana_cost'] == '{T}' and ability['index'] == 0
    proxy = type('ActivatedOracleProxy', (), {'id': coating, 'oracle_text': ability['text'],
                                            'mana_cost': '', 'name': state.cards[coating].name})()
    spec = build_ability_spec(state, proxy, owner, action_targets=action['targets'], report_unsupported=False)
    assert spec.effect.key != 'noop', {'real_clause': ability['text'], 'actual_effect': spec.effect.key}
    state = checked_action(state, RulesEngine(), owner, action)
    assert state.stack[-1].source_card_id == coating and state.cards[coating].tapped
    assert resolve_top_of_stack(state)
    assert 'Artifact' in effective_types(state, pool)
    state, _ = cast_vaults(state, owner)
    assert not resolve_top_of_stack(state)
    pending = state.pending_mechanic_choice
    assert pending['player_id'] == owner and pool in pending['options']
    assert state.cards[steel].zone == Zone.GRAVEYARD
    state = choose(snapshot(state), owner, pool)
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'land_entry' and pending['player_id'] == owner
    assert pending['entry_card_id'] == steel and pending['options'] == ['tapped', 'pay_two_life']
    assert state.cards[steel].zone == Zone.GRAVEYARD
    before = state.players[owner].life
    state = choose(snapshot(state), owner, 'pay_two_life')
    assert state.players[owner].life == before-2
    assert state.cards[steel].zone == Zone.BATTLEFIELD and not state.cards[steel].tapped
    assert state.cards[steel].controller == owner
    assert state.cards[steel].name == 'Breeding Pool'
    assert snapshot(state).cards[steel].oracle_text == raw_card('Breeding Pool')['oracle_text']


@pytest.mark.parametrize('owner', [1, 2])
def test_returning_real_steel_requires_native_copy_entry_with_existing_real_artifact(owner):
    names = ('Open the Vaults', 'Sculpting Steel', 'Sol Ring')
    state = position(names, names, active=owner)
    target = place(state, 'Sol Ring', Zone.BATTLEFIELD, owner)
    steel = place(state, 'Sculpting Steel', Zone.GRAVEYARD, owner)
    state, _ = cast_vaults(state, owner)
    assert not resolve_top_of_stack(state)
    pending = state.pending_mechanic_choice
    assert pending['player_id'] == owner and target in pending['options']
    assert state.cards[steel].zone == Zone.GRAVEYARD
    state = choose(snapshot(state), owner, target)
    assert state.cards[steel].zone == Zone.BATTLEFIELD and state.cards[steel].controller == owner
    assert state.cards[steel].oracle_text == raw_card('Sol Ring')['oracle_text']
    assert state.cards[steel].name == 'Sol Ring'
