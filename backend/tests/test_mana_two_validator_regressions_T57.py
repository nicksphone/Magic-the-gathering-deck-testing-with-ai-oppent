"""Genuine paused payments; no selected-plan/frame injection or print repair."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import ActionRejected
from tests.mana_canonical_76 import entry
from tests.test_forge_human_replacement_order import (
    act, balances, card_entry, choose, fingerprint, finish_stack, setup,
)


FIXTURES = Path(__file__).parent / 'fixtures'
RAW = {
    'Skirge Familiar': ('cost_reservation_overlap/canonical.json',
        'fd6c5a98c5d88557589f6fa5f7b87dcb33a88be5bff76aa6a316595d1aa1f9ec'),
    'Sphere of Resistance': ('announced_costs/sphere-of-resistance.json',
        '3058e2118924a8ac49550c38ce4c934f262274f08e28d808998f8cb1baf6f98a'),
    'Karplusan Forest': ('mana_two_p2_T57/karplusan-forest.raw.json',
        '89fccda9e63cb9daa31fa854fa804b316d8ac459d33ce23689b162394fe2ab6c'),
    'Wild Growth': ('mana_two_p2_T57/wild-growth.raw.json',
        'f719a52e0a85fe31979867341ee142e7762e4a319a7a27fec2ed4422f415f2b0'),
}


def official(name, quantity=1):
    path, digest = RAW[name]
    data = (FIXTURES / path).read_bytes()
    assert hashlib.sha256(data).hexdigest() == digest
    value = json.loads(data)
    raw = value[name] if name == 'Skirge Familiar' else value
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['id'] and raw['oracle_id'] and len(raw) > 50
    return card_entry(raw, quantity)


def born_setup(seat, extras, monkeypatch, record_property, initial_color):
    original = MatchFactory.from_decks

    def from_full_decks(a, b, **kwargs):
        state = original([*a, *deepcopy(extras)], [*b, *deepcopy(extras)], **kwargs)
        assert initial_color in {'C', 'R', 'G'}
        assert not any(state.players[seat].mana_pool.values())
        assert state.spells_cast_this_turn.get(seat, 0) == 0
        # Initial resource pose, before the first genuine Salve cast/payment.
        state.players[seat].mana_pool[initial_color] = 1
        return state

    # Add full prints before the actual Factory captures stock and knowledge.
    with monkeypatch.context() as birth:
        birth.setattr(MatchFactory, 'from_decks', staticmethod(from_full_decks))
        state, forges, _, _ = setup(seat)
    assert state.sideboard_facts
    player = state.players[seat]
    assert player.mana_pool[initial_color] == 1 and player.mana_pool['W'] == 0
    assert sum(player.mana_pool.values()) == 1
    assert state.spells_cast_this_turn[seat] == 2
    assert player.prevent_damage_shield == 6 and set(balances(state).values()) == {3}
    record_property('initial_budget_survived_two_real_W_only_Salves',
                    json.dumps({'color': initial_color, 'remaining': 1, 'W': 0,
                                'actual_spells_cast': 2, 'shield': 6}, sort_keys=True))
    return state, forges


def place(state, cid, zone):
    card = state.cards[cid]
    player = state.players[card.controller if card.zone == Zone.BATTLEFIELD else card.owner]
    getattr(player, card.zone.value).remove(cid)
    card.move_to_zone(zone)
    getattr(state.players[card.owner], zone.value).append(cid)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, cid)


def owned(state, seat, name):
    return [card.id for card in state.cards.values()
            if card.owner == seat and card.name == name]


def json_restore(state):
    before = fingerprint(state)
    restored = deserialize_match_snapshot(json.loads(json.dumps(serialize_match_snapshot(state))))
    assert fingerprint(restored) == before and fingerprint(state) == before
    return restored


def assert_replay_rejected(state, seat, receipt):
    before = fingerprint(state)
    with pytest.raises(ActionRejected):
        choose(state, seat, receipt)
    assert fingerprint(state) == before


def observe_real_freeze(monkeypatch, record_property, seat, *, familiar=None,
                        payments=(), bolt=None, forge=None, initial_color=None, growth=None):
    from rules_engine import mana_continuation
    original = mana_continuation._freeze
    witnessed = []

    def observe(candidate):
        # Read the genuine producer only; no context/frame/plan assignment.
        frames = mana_continuation._SESSION.get()['frames']
        op = 'cast' if familiar is not None else 'bulk_mana'
        if frames[0].get('op') == op:
            assert candidate.pending_replacement_choice['player_id'] == seat
            if op == 'cast':
                data = frames[1]['data']
                assert data['req']['generic'] == 3 and data['req']['R'] == 1
                assert bolt in data['reserved_card_ids'] and data['in_flight'] is True
                assert len(set(payments)) == 2 and candidate.cards[bolt].zone == Zone.HAND
                assert frames[-1]['source']['card_id'] == forge
                assert frames[-1]['output'] == {'R': 1}
                if initial_color == 'C':
                    assert data['cursor'] == 0 and data['paid_prefix'] == []
                    assert [row['source']['card_id'] for row in data['steps']] == [forge, familiar, familiar]
                    assert all(row['kind'] == 'paid' and row['selector'] == 'B'
                               for row in data['steps'][1:])
                    assert all(candidate.cards[cid].zone == Zone.HAND for cid in payments)
                    label = 'cast_C1_real_R_pause_two_locked_unpaid_steps'
                else:
                    assert initial_color == 'R'
                    steps, cursor, prefix = data['steps'], data['cursor'], data['paid_prefix']
                    assert len(steps) == 3 and type(cursor) is int and 0 <= cursor < 3
                    assert [row['source']['card_id'] for row in steps].count(familiar) == 2
                    assert [row['source']['card_id'] for row in steps].count(forge) == 1
                    assert steps[cursor]['source']['card_id'] == forge
                    assert steps[cursor]['kind'] == 'paid' and steps[cursor]['selector'] == 'R'
                    assert all(row['kind'] == 'paid' and row['selector'] == 'B'
                               for index, row in enumerate(steps) if index != cursor)
                    assert len(prefix) == cursor
                    for index, row in enumerate(prefix):
                        assert row['source'] == steps[index]['source']
                        assert row['source']['card_id'] == familiar
                        assert row['pool_after']['R'] == 1 and row['pool_after']['B'] == index + 1
                        assert sum(row['pool_after'].values()) == index + 2
                    assert sum(candidate.cards[cid].zone == Zone.GRAVEYARD for cid in payments) == cursor
                    assert sum(candidate.cards[cid].zone == Zone.HAND for cid in payments) == 2 - cursor
                    pool = candidate.players[seat].mana_pool
                    assert pool['R'] == 2 and pool['B'] == cursor and sum(pool.values()) == cursor + 2
                    record_property('actual_R1_cursor', str(cursor))
                    label = 'cast_R1_real_R_pause_index_bound_actual_plan_and_prefix'
            else:
                assert frames[0]['data']['roster'][0]['amount'] == 2
                assert frames[-1]['output'] == {'G': 1}
                bonus, = frames[-1]['captured_bonus']
                assert bonus[0] == seat and bonus[1] == growth and bonus[4] == {'G': 1}
                label = 'bulk_G1_base_G_plus_actual_bonus_G'
            witnessed.append(label)
            record_property('genuine_prevalidation_witness', label)
        return original(candidate)

    monkeypatch.setattr(mana_continuation, '_freeze', observe)
    return witnessed


def exercise_reusable_source(seat, monkeypatch, record_property, initial_color):
    state, forges = born_setup(seat, [official('Skirge Familiar'),
        official('Sphere of Resistance', 3), entry('Island', 2)], monkeypatch,
        record_property, initial_color)
    familiar, = owned(state, seat, 'Skirge Familiar')
    bolt, = owned(state, seat, 'Lightning Bolt')
    payments = owned(state, seat, 'Island')
    spheres = owned(state, seat, 'Sphere of Resistance')
    assert len(set(payments)) == 2 and len(set(spheres)) == 3
    # Established-board pose: only two expendable cards; Bolt must be reserved.
    for cid in list(state.players[seat].hand):
        place(state, cid, Zone.LIBRARY)
    for cid in forges:
        place(state, cid, Zone.LIBRARY)
    for cid in [familiar, forges[0], *spheres]:
        place(state, cid, Zone.BATTLEFIELD)
    for cid in [bolt, *payments]:
        place(state, cid, Zone.HAND)
    before, initial = fingerprint(state), balances(state)
    witnessed = observe_real_freeze(monkeypatch, record_property, seat, familiar=familiar,
        payments=payments, bolt=bolt, forge=forges[0], initial_color=initial_color)
    # Three real Spheres make Bolt {3}{R}. Never edit the selected native plan.
    paused = act(state, seat, {'type': 'cast_spell', 'card_id': bolt,
        'cost_choice': {'id': 'base'}, 'targets': {'target_player': 3-seat}})
    assert fingerprint(state) == before
    if paused.mana_continuation is None:
        # Only the R-funded secondary admits genuine harmless free-C completion.
        # No exception is caught or converted into this alternate observation.
        assert initial_color == 'R' and witnessed == []
        assert paused.pending_replacement_choice is None
        assert balances(paused) == initial and paused.players[seat].prevent_damage_shield == 6
        assert paused.players[seat].life == 20 and paused.cards[forges[0]].tapped
        assert all(paused.cards[cid].zone == Zone.GRAVEYARD for cid in payments)
        assert len(paused.stack) == 1 and paused.stack[0].source_card_id == bolt
        assert paused.stack[0].controller == seat and paused.cards[bolt].zone == Zone.STACK
        assert not any(paused.players[seat].mana_pool.values()) and not paused.players[seat].hand
        assert paused.spells_cast_this_turn[seat] == 3
        new_log = paused.log[len(state.log):]
        player, source = paused.players[seat], paused.cards[forges[0]]
        assert f'{player.name} activates {source.name} for 1 C.' in new_log
        assert f'{player.name} activates {source.name} for 1 R.' not in new_log
        record_property('actual_R1_path', 'harmless_native_free_C_completion')
        return
    owner, payment, activation = paused.mana_continuation['frames']
    data = payment['data']
    assert owner['op'] == 'cast' and data['req']['generic'] == 3 and data['req']['R'] == 1
    assert data['in_flight'] is True and len(witnessed) == 1
    if initial_color == 'C':
        assert data['cursor'] == 0 and data['paid_prefix'] == []
        assert all(paused.cards[cid].zone == Zone.HAND for cid in payments)
        assert set(paused.players[seat].hand) == {bolt, *payments}
        assert paused.players[seat].mana_pool['C'] == paused.players[seat].mana_pool['R'] == 1
    else:
        cursor = data['cursor']
        assert len(data['paid_prefix']) == cursor
        assert sum(paused.cards[cid].zone == Zone.GRAVEYARD for cid in payments) == cursor
        assert sum(paused.cards[cid].zone == Zone.HAND for cid in payments) == 2 - cursor
        assert set(paused.players[seat].hand) == {bolt, *(
            cid for cid in payments if paused.cards[cid].zone == Zone.HAND)}
        record_property('actual_R1_path', 'native_R_pause_with_actual_index_bound_prefix')
    assert paused.cards[bolt].zone == Zone.HAND
    assert activation['source']['card_id'] == forges[0] and paused.cards[forges[0]].tapped
    assert not paused.stack and balances(paused) == initial
    receipt = next(iter(initial))
    finished = choose(json_restore(paused), seat, receipt)
    assert finished.mana_continuation is None and finished.pending_replacement_choice is None
    assert len(finished.stack) == 1 and finished.stack[0].source_card_id == bolt
    assert finished.stack[0].controller == seat and finished.cards[bolt].zone == Zone.STACK
    assert all(finished.cards[cid].zone == Zone.GRAVEYARD for cid in payments)
    assert not any(finished.players[seat].mana_pool.values())
    assert finished.spells_cast_this_turn[seat] == 3
    assert finished.players[seat].life == 20 and finished.players[seat].prevent_damage_shield == 5
    assert balances(finished) == {key: value - int(key == receipt) for key, value in initial.items()}
    assert_replay_rejected(finished, seat, receipt)
    assert fingerprint(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_C1_requires_real_R_pause_with_two_unpaid_Familiar_steps(seat, monkeypatch, record_property):
    exercise_reusable_source(seat, monkeypatch, record_property, 'C')


@pytest.mark.parametrize('seat', [1, 2])
def test_R1_preserves_paid_prefix_or_verifies_harmless_free_C_completion(seat, monkeypatch, record_property):
    exercise_reusable_source(seat, monkeypatch, record_property, 'R')


@pytest.mark.parametrize('seat', [1, 2])
def test_bulk_same_color_bonus_survives_native_pause_json_and_atomic_negatives(seat, monkeypatch, record_property):
    state, forges = born_setup(seat, [official('Karplusan Forest'), official('Wild Growth')],
                               monkeypatch, record_property, 'G')
    land, = owned(state, seat, 'Karplusan Forest')
    growth, = owned(state, seat, 'Wild Growth')
    for cid in forges:
        place(state, cid, Zone.LIBRARY)
    place(state, land, Zone.BATTLEFIELD)
    place(state, growth, Zone.HAND)
    state = act(state, seat, {'type': 'cast_spell', 'card_id': growth,
        'cost_choice': {'id': 'base'}, 'targets': {'target_card_id': land}})
    state = finish_stack(state)
    assert state.cards[growth].attached_to == land and state.cards[growth].zone == Zone.BATTLEFIELD
    assert state.players[seat].mana_pool['G'] == 0 and not state.stack
    assert state.spells_cast_this_turn[seat] == 3
    before, initial = fingerprint(state), balances(state)
    observe_real_freeze(monkeypatch, record_property, seat, growth=growth)
    paused = act(state, seat, {'type': 'tap_lands_bulk', 'land_name': 'Karplusan Forest',
                              'count': 1, 'color': 'G'})
    assert fingerprint(state) == before
    owner, activation = paused.mana_continuation['frames']
    assert owner['data']['roster'][0]['amount'] == 2
    assert activation['output'] == {'G': 1}
    bonus, = activation['captured_bonus']
    assert bonus[0] == seat and bonus[1] == growth and bonus[4] == {'G': 1}
    assert paused.players[seat].mana_pool['G'] == 1 and balances(paused) == initial
    assert paused.cards[land].tapped
    damaged = json.loads(json.dumps(serialize_match_snapshot(paused)))
    damaged['mana_continuation']['frames'][0]['data']['roster'][0]['amount'] += 1
    paused_before = fingerprint(paused)
    with pytest.raises(ActionRejected):
        deserialize_match_snapshot(damaged)
    assert fingerprint(paused) == paused_before
    receipt = next(iter(initial))
    finished = choose(json_restore(paused), seat, receipt)
    assert finished.players[seat].mana_pool['G'] == 2 and finished.cards[land].tapped
    assert finished.mana_continuation is None and finished.pending_replacement_choice is None
    assert finished.players[seat].life == 20 and finished.players[seat].prevent_damage_shield == 5
    assert balances(finished) == {key: value - int(key == receipt) for key, value in initial.items()}
    assert not finished.stack
    assert_replay_rejected(finished, seat, receipt)
    assert fingerprint(state) == before
