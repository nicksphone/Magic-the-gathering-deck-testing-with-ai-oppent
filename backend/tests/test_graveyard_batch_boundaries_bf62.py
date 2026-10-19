"""Real protection and selectable multi-owner pre-entry replacement boundaries."""
from copy import deepcopy

import pytest

from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.graveyard_batch_boundary_support_bf62 import SOURCES, place_all, position, raw_card
from tests.graveyard_batch_native_support_bf62 import cast_vaults, choose, locate, place, snapshot


@pytest.mark.parametrize('name', sorted(SOURCES))
def test_extra_full_raw_facts_and_independence_reach_real_factory(name):
    raw = raw_card(name)
    state = position((name,))
    card = state.cards[locate(state, name)]
    assert card.name == raw['name'] and card.type_line == raw['type_line']
    assert card.oracle_text == raw.get('oracle_text', '')
    assert card.mana_cost == raw.get('mana_cost', '')
    assert card.colors == raw.get('colors', [])
    assert card.printed_power == raw.get('power') and card.printed_toughness == raw.get('toughness')
    assert card.owner == card.controller == 1
    changed = raw_card(name)
    changed['legalities']['modern'] = 'local-test-mutation'
    assert changed['legalities'] is not raw['legalities'] and raw_card(name) == raw
    assert len(state.starting_decks[1]) > 0
    assert snapshot(state).cards[card.id].oracle_text == raw['oracle_text']


@pytest.mark.parametrize('caster', [1, 2])
@pytest.mark.parametrize('protected_owner', [1, 2])
def test_protection_only_recipient_keeps_both_real_auras_in_graveyards(caster, protected_owner):
    names = ('Open the Vaults', 'Rancor', 'Progenitus', 'Sol Ring')
    state = position(names, names, active=caster)
    protected = place(state, 'Progenitus', Zone.BATTLEFIELD, protected_owner)
    auras = [place(state, 'Rancor', Zone.GRAVEYARD, owner) for owner in (1, 2)]
    artifact = place(state, 'Sol Ring', Zone.GRAVEYARD)
    state, _ = cast_vaults(state, caster)
    assert resolve_top_of_stack(state)
    assert state.pending_mechanic_choice is None and state.pending_replacement_choice is None
    assert state.cards[artifact].zone == Zone.BATTLEFIELD
    assert all(state.cards[cid].zone == Zone.GRAVEYARD for cid in auras)
    assert all(state.cards[cid].attached_to is None for cid in auras)
    assert state.cards[protected].oracle_text == raw_card('Progenitus')['oracle_text']
    assert snapshot(state).cards[protected].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('caster', [1, 2])
@pytest.mark.parametrize('protected_owner', [1, 2])
def test_mandatory_auras_exclude_protection_but_allow_foreign_hexproof_before_commit(caster, protected_owner):
    names = ('Open the Vaults', 'Rancor', 'Progenitus', 'Slippery Bogle', 'Sol Ring')
    state = position(names, names, active=caster)
    protected = place(state, 'Progenitus', Zone.BATTLEFIELD, protected_owner)
    hexproof = place(state, 'Slippery Bogle', Zone.BATTLEFIELD, 3-protected_owner)
    auras = {owner: place(state, 'Rancor', Zone.GRAVEYARD, owner) for owner in (1, 2)}
    artifact = place(state, 'Sol Ring', Zone.GRAVEYARD)
    state, _ = cast_vaults(state, caster)
    assert not resolve_top_of_stack(state)
    for owner in (caster, 3-caster):
        pending = state.pending_mechanic_choice
        assert pending['player_id'] == owner and pending['options'] == [hexproof]
        assert pending['entry_card_id'] == auras[owner]
        assert all(state.cards[cid].zone == Zone.GRAVEYARD for cid in [artifact, *auras.values()])
        state = snapshot(state)
        before = deepcopy(state)
        with pytest.raises(ActionRejected):
            choose(state, owner, protected)
        assert state.rng.getstate() == before.rng.getstate()
        assert all(getattr(state, field) == getattr(before, field)
                   for field in state.__dataclass_fields__ if field != 'rng')
        state = choose(state, owner, hexproof)
    assert state.cards[artifact].zone == Zone.BATTLEFIELD
    for owner, cid in auras.items():
        assert state.cards[cid].zone == Zone.BATTLEFIELD
        assert state.cards[cid].controller == owner and state.cards[cid].attached_to == hexproof
    assert snapshot(state).cards[auras[2]].attached_to == hexproof


def replacement_action(state, owner, source_id):
    return checked_action(state, RulesEngine(), owner,
                          {'type': 'choose_replacement', 'replacement_source_id': source_id})


@pytest.mark.parametrize('caster', [1, 2])
@pytest.mark.parametrize('operations,expected', [
    (('add', 'add'), 10), (('double', 'add'), 8), (('add', 'double'), 9),
])
def test_two_scales_and_season_each_owner_select_order_before_any_batch_commit(caster, operations, expected):
    names = ('Open the Vaults', 'Triskelion', 'Sol Ring',
             'Hardened Scales', 'Hardened Scales', 'Doubling Season')
    state = position(names, names, active=caster)
    creatures = {owner: place(state, 'Triskelion', Zone.GRAVEYARD, owner) for owner in (1, 2)}
    rings = [place(state, 'Sol Ring', Zone.GRAVEYARD, owner) for owner in (1, 2)]
    resident = {owner: [*place_all(state, 'Hardened Scales', owner),
                        *place_all(state, 'Doubling Season', owner)] for owner in (1, 2)}
    state, source = cast_vaults(state, caster)
    assert not resolve_top_of_stack(state)
    frame_id = None
    for owner in (caster, 3-caster):
        seen = []
        for index, operation in enumerate(operations):
            pending = state.pending_replacement_choice
            assert pending is not None and pending['player_id'] == owner
            assert pending['counter_payload']['target_card_id'] == creatures[owner]
            assert len(pending['options']) == 3-index
            assert {option['source_card_id'] for option in pending['options']} <= set(resident[owner])
            payload = pending['counter_payload']['entry_completion_payload']
            frame = payload['__resolving_item']
            frame_id = frame_id or frame['id']
            assert frame['id'] == frame_id and frame['source_card_id'] == source
            assert frame['controller'] == caster
            assert all(state.cards[cid].zone == Zone.GRAVEYARD for cid in [*creatures.values(), *rings])
            assert all(not state.cards[cid].counters for cid in creatures.values())
            option = next(row for row in pending['options'] if row['operation'] == operation)
            assert option['source_id'] not in seen
            seen.append(option['source_id'])
            state = snapshot(state)
            before = deepcopy(state)
            with pytest.raises(ActionRejected):
                replacement_action(state, 3-owner, option['source_id'])
            assert state.rng.getstate() == before.rng.getstate()
            assert all(getattr(state, field) == getattr(before, field)
                       for field in state.__dataclass_fields__ if field != 'rng')
            state = replacement_action(state, owner, option['source_id'])
    assert state.pending_replacement_choice is None and state.pending_mechanic_choice is None
    for owner, cid in creatures.items():
        assert state.cards[cid].zone == Zone.BATTLEFIELD and state.cards[cid].controller == owner
        assert state.cards[cid].counters['+1/+1'] == expected
    assert all(state.cards[cid].zone == Zone.BATTLEFIELD for cid in rings)
    assert snapshot(state).cards[creatures[1]].counters['+1/+1'] == expected
