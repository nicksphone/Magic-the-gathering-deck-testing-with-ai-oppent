"""Actual copy choices precede owner-bound counters and deferred payments."""
from copy import deepcopy

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.graveyard_batch_native_support_bf62 import cast_vaults, choose, place, snapshot
from tests.test_entry_copy_native_936 import cast, position
from tests.test_graveyard_batch_boundaries_bf62 import replacement_action
from tests.graveyard_batch_boundary_support_bf62 import place_all


def graveyard_copies(state, name, seat):
    ids = [c.id for c in state.cards.values() if c.name == name and c.owner == seat]
    for cid in ids:
        for player in state.players.values():
            for field in ('hand', 'library', 'graveyard', 'exile', 'battlefield'):
                if cid in getattr(player, field):
                    getattr(player, field).remove(cid)
        state.cards[cid].move_to_zone(Zone.GRAVEYARD)
        state.players[seat].graveyard.append(cid)
    return ids


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('route', ['spell', 'vaults'])
@pytest.mark.parametrize('order,expected', [
    (('add', 'add'), 10), (('double', 'add'), 8), (('add', 'double'), 9),
])
def test_copied_triskelion_uses_its_entry_seed_and_real_selectable_replacements(seat, route, order, expected):
    names = ['Sculpting Steel', 'Open the Vaults', 'Triskelion',
             'Hardened Scales', 'Hardened Scales', 'Doubling Season']
    state = position(names, names, seat)
    target = place(state, 'Triskelion', Zone.BATTLEFIELD, 3-seat)
    for name in ('Hardened Scales', 'Doubling Season'):
        place_all(state, name, seat)
    if route == 'spell':
        state, steel = cast(state, seat, 'Sculpting Steel')
        old_zone = Zone.STACK
    else:
        steel = place(state, 'Sculpting Steel', Zone.GRAVEYARD, seat)
        state, _ = cast_vaults(state, seat)
        old_zone = Zone.GRAVEYARD
    assert not resolve_top_of_stack(state)
    state = choose(snapshot(state), seat, target)
    for operation in order:
        pending = state.pending_replacement_choice
        assert pending is not None and pending['player_id'] == seat
        assert pending['counter_payload']['target_card_id'] == steel
        assert state.cards[steel].zone == old_zone
        assert state.cards[steel].name == 'Sculpting Steel' and not state.cards[steel].counters
        option = next(row for row in pending['options'] if row['operation'] == operation)
        state = replacement_action(snapshot(state), seat, option['source_id'])
    assert not state.pending_replacement_choice and not state.pending_mechanic_choice
    assert state.cards[steel].name == 'Triskelion' and state.cards[steel].zone == Zone.BATTLEFIELD
    assert state.cards[steel].counters['+1/+1'] == expected
    assert snapshot(state).cards[steel].printed_characteristics['name'] == 'Sculpting Steel'


@pytest.mark.parametrize('seat', [1, 2])
def test_two_real_copied_shocklands_reserve_but_do_not_pay_before_all_choices(seat):
    names = ['Sculpting Steel', 'Sculpting Steel', 'Open the Vaults',
             'Liquimetal Coating', 'Breeding Pool']
    state = position(names, names, seat)
    pool = place(state, 'Breeding Pool', Zone.BATTLEFIELD, 3-seat)
    coating = place(state, 'Liquimetal Coating', Zone.BATTLEFIELD, seat)
    state = checked_action(state, RulesEngine(), seat, {'type': 'activate_ability',
        'card_id': coating, 'ability_index': 0, 'targets': {'target_card_id': pool}})
    assert resolve_top_of_stack(state)
    steels = graveyard_copies(state, 'Sculpting Steel', seat)
    assert len(steels) == 2 and len(set(steels)) == 2
    state, _ = cast_vaults(state, seat)
    assert not resolve_top_of_stack(state)
    state = choose(snapshot(state), seat, pool)
    assert state.pending_mechanic_choice['kind'] == 'entry_copy'
    state = choose(snapshot(state), seat, pool)
    before = state.players[seat].life
    assert state.pending_mechanic_choice['kind'] == 'land_entry'
    state = choose(snapshot(state), seat, 'pay_two_life')
    assert state.pending_mechanic_choice['kind'] == 'land_entry'
    assert state.players[seat].life == before
    assert all(state.cards[cid].zone == Zone.GRAVEYARD for cid in steels)
    state = choose(snapshot(state), seat, 'pay_two_life')
    assert state.players[seat].life == before-4
    assert all(state.cards[cid].zone == Zone.BATTLEFIELD and not state.cards[cid].tapped for cid in steels)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mutation', ['projection', 'choice_values', 'missing_choice'])
def test_pending_counter_copy_projection_is_exact_and_tamper_rejects_atomically(seat, mutation):
    names = ['Sculpting Steel', 'Open the Vaults', 'Triskelion',
             'Hardened Scales', 'Hardened Scales', 'Doubling Season']
    state = position(names, names, seat)
    target = place(state, 'Triskelion', Zone.BATTLEFIELD, 3-seat)
    for name in ('Hardened Scales', 'Doubling Season'):
        place_all(state, name, seat)
    steel = place(state, 'Sculpting Steel', Zone.GRAVEYARD, seat)
    state, _ = cast_vaults(state, seat)
    assert not resolve_top_of_stack(state)
    state = choose(snapshot(state), seat, target)
    pending = state.pending_replacement_choice
    assert pending and state.cards[steel].zone == Zone.GRAVEYARD
    data = pending['counter_payload']
    if mutation == 'projection':
        data['entry_targets'][0]['projection']['oracle_text'] = ''
    else:
        plan = data['entry_completion_payload']['__entry_copy_plan']
        if mutation == 'missing_choice':
            plan['entries'][0]['choice'] = None
            data['entry_options']['__entry_copy_plan']['entries'][0]['choice'] = None
        else:
            plan['entries'][0]['choice']['values']['name'] = 'protocol-tamper'
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        replacement_action(state, seat, pending['options'][0]['source_id'])
    assert serialize_match_snapshot(state) == before
