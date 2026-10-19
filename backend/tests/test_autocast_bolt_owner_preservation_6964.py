"""Desired real Bolt cast ownership using its actual seeded opening hand.

Reuse the complete canonical setup and its two paid Salve receipts. Both seats
already draw their own Bolt; no extra zone transition or card is needed.
Follow its real locked payment plan, comparing native and JSON-restored human
continuations without forcing the first mana activation to match the cost.
"""
from copy import deepcopy
import json

import pytest

from game_state.serializers import (
    deserialize_match_snapshot,
    serialize_match,
    serialize_match_snapshot,
)
from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import ActionRejected
from tests.library_canonical_fixtures import raw_card
from tests.mana_canonical_76 import raw_card as mana_raw_card
from tests.test_forge_human_replacement_order import (
    act,
    assert_initial_choice,
    balances,
    choose,
    fingerprint,
    finish_stack,
    setup,
)


def _json_restore(state):
    original = fingerprint(state)
    payload = json.loads(json.dumps(serialize_match_snapshot(state)))
    encoded = json.dumps(payload, sort_keys=True)
    restored = deserialize_match_snapshot(payload)
    assert fingerprint(restored) == original
    assert fingerprint(state) == original
    assert json.dumps(payload, sort_keys=True) == encoded
    return restored


def _assert_owner_private(state):
    def inspect(value):
        if isinstance(value, dict):
            # These are EXISTING private-envelope keys, not proposed cast fields.
            assert 'mana_continuation' not in value
            assert 'frames' not in value
            for child in value.values():
                inspect(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                inspect(child)

    before = fingerprint(state)
    for viewer in (1, 2):
        public = serialize_match(state, look_players=(viewer,))
        inspect(public)
        assert len(public['stack']) == len(state.stack)
        if state.stack:
            assert public['stack'][0]['id'] == state.stack[0].id
            assert public['stack'][0]['controller'] == state.stack[0].controller
    assert fingerprint(state) == before


def _pause_targeted_bolt(seat):
    state, forges, _, opponent_bolt = setup(seat)
    stock = deepcopy(state.sideboard_facts)
    cards = set(state.cards)
    own = [card for card in state.cards.values()
           if card.name == 'Lightning Bolt' and card.owner == seat]
    assert len(own) == 1
    bolt = own[0]
    assert bolt.id != opponent_bolt
    assert bolt.controller == seat and bolt.zone == Zone.HAND
    assert bolt.id in state.players[seat].hand
    raw = raw_card('Lightning Bolt')
    assert bolt.mana_cost == raw['mana_cost'] == '{R}'
    assert bolt.oracle_text == raw['oracle_text']
    assert bolt.type_line == raw['type_line'] == 'Instant'
    assert bolt.colors == raw['colors']

    # Seed 618 already puts this native physical object in the opening hand.
    assert state.sideboard_facts == stock and set(state.cards) == cards
    assert state.players[seat].mana_pool['R'] == 0
    assert state.players[seat].life == state.players[3-seat].life == 20
    assert not any(state.cards[cid].tapped for cid in forges)
    assert not state.stack and not state.pending_replacement_choice
    original_balances = balances(state)
    assert list(original_balances.values()) == [3, 3]
    forge = mana_raw_card('Battlefield Forge')
    assert forge['oracle_text'].splitlines() == [
        '{T}: Add {C}.',
        '{T}: Add {R} or {W}. This land deals 1 damage to you.',
    ]
    for cid in forges:
        card = state.cards[cid]
        assert card.name == forge['name'] == 'Battlefield Forge'
        assert card.oracle_text == forge['oracle_text']
        assert card.type_line == forge['type_line'] == 'Land'
        assert card.colors == forge['colors'] == []
        assert card.owner == card.controller == seat and card.zone == Zone.BATTLEFIELD
    assert not any(state.players[seat].mana_pool.values())
    assert not any(state.players[seat].snow_mana_pool.values())
    proof = {
        'seat': seat, 'bolt': bolt.id, 'forges': tuple(forges),
        'stock': stock, 'cards': cards, 'printed': deepcopy(bolt.printed_characteristics),
        'hand_reference': (object_incarnation(bolt), bolt.zone_change_sequence),
        'balances': original_balances,
        'cast_counts': dict(state.spells_cast_this_turn),
        'pool': dict(state.players[seat].mana_pool),
        'snow': dict(state.players[seat].snow_mana_pool),
        'native_root': state, 'native_root_fingerprint': fingerprint(state),
        'bolt_birth': deepcopy(serialize_match_snapshot(state)['cards'][bolt.id]),
    }
    proof['cast_action'] = {
        'type': 'cast_spell', 'card_id': bolt.id,
        'cost_choice': {'id': 'base'}, 'targets': {'target_player': 3-seat},
    }
    result = act(state, seat, deepcopy(proof['cast_action']))
    owner, payment, activation = result.mana_continuation['frames']
    assert [owner['tag'], payment['tag'], activation['tag']] == [
        'owner', 'payment', 'mana_activation',
    ]
    proof['payment_contract'] = deepcopy(owner['data']['payment_contract'])
    contract = proof['payment_contract']
    assert contract['req'] == {
        'generic': 0, 'W': 0, 'U': 0, 'B': 0, 'R': 1,
        'G': 0, 'C': 0, 'S': 0, 'life': 0,
    }
    assert contract['resource_plan'] is None and contract['protected_life'] == 0
    assert not any(contract['snow_spent'].values())
    steps = contract['steps']
    # This is the observed native choice, never a replacement/forced plan.
    assert len(steps) == len(forges) == 2
    assert [step['selector'] for step in steps] == ['W', 'R']
    assert {step['source']['card_id'] for step in steps} == set(forges)
    for step in steps:
        card = state.cards[step['source']['card_id']]
        assert step['kind'] == 'paid' and step['ability_index'] == 1
        assert step['amount'] == 0 and step['spec'] is None
        assert step['source'] == {
            'card_id': card.id, 'incarnation': object_incarnation(card),
            'zone_change_sequence': card.zone_change_sequence,
            'zone': 'battlefield', 'controller': seat,
        }
    _assert_paused(result, proof)
    return result, proof


def _expected_pool(proof, produced, *, spent=False):
    pool = dict(proof['pool'])
    for step in proof['payment_contract']['steps'][:produced]:
        pool[step['selector']] += 1
    if spent:
        pool['R'] -= 1
    return pool


def _expected_balances(proof, selected, prevented):
    return {key: value - (prevented if index == selected else 0)
            for index, (key, value) in enumerate(proof['balances'].items())}


def _assert_same_native(state, control):
    left = serialize_match_snapshot(state)
    right = serialize_match_snapshot(control)
    # Do not normalize printed/cache/copiable facts or private owner frames.
    for key in ('cards', 'players', 'stack', 'numeric_prevention_shields',
                'sideboard_facts', 'spells_cast_this_turn', 'mana_continuation',
                'pending_replacement_choice', 'pending_mechanic_choice',
                'pending_trigger_order', 'trigger_staging', 'trigger_staging_event',
                'staged_triggers', 'next_object_id', 'priority_player'):
        assert left[key] == right[key], key


def _assert_paused(state, proof, selected=0, index=0):
    seat, bolt_id = proof['seat'], proof['bolt']
    if index == 0:
        assert_initial_choice(state, seat, proof['balances'])
    owner, payment, activation = state.mana_continuation['frames']
    contract = proof['payment_contract']
    assert owner['op'] == 'cast' and owner['payer'] == seat
    assert owner['data']['payment_contract'] == contract
    assert all(payment['data'][key] == value for key, value in contract.items())
    assert payment['payer'] == seat and payment['data']['cursor'] == index
    assert payment['data']['in_flight'] is True and payment['data']['life_paid'] is True
    assert owner['data']['source'] == {
        'card_id': bolt_id, 'incarnation': proof['hand_reference'][0],
        'zone_change_sequence': proof['hand_reference'][1],
        'zone': 'hand', 'controller': seat,
    }
    assert owner['data']['action_targets'] == {'target_player': 3-seat}
    assert owner['data']['target_references'] == {'version': 1, 'targets': {}}
    prefix = payment['data']['paid_prefix']
    assert len(prefix) == index
    for number, row in enumerate(prefix):
        assert row['source'] == contract['steps'][number]['source']
        assert row['pool_after'] == _expected_pool(proof, number + 1)
        assert row['snow_after'] == proof['snow']
    step = contract['steps'][index]
    assert activation['source'] == step['source'] and activation['payer'] == seat
    assert activation['ability_index'] == step['ability_index']
    assert activation['color'] == step['selector']
    assert activation['output'] == {step['selector']: 1}
    assert activation['captured_bonus'] == [] and activation['bonus_cursor'] == 0
    pending = state.pending_replacement_choice
    assert pending['player_id'] == seat and pending['event'] == 'damage_to_player'
    assert {option['source_id'] for option in pending['options']} == {
        'numeric-prevention:' + receipt for receipt in proof['balances']}
    assert balances(state) == _expected_balances(proof, selected, index)
    assert state.players[seat].prevent_damage_shield == 6 - index
    assert state.players[seat].life == 20
    bolt = state.cards[bolt_id]
    assert not state.stack and bolt.zone == Zone.HAND
    assert bolt_id in state.players[seat].hand
    assert bolt.owner == bolt.controller == seat
    assert (object_incarnation(bolt), bolt.zone_change_sequence) == proof['hand_reference']
    assert bolt.printed_characteristics == proof['printed']
    assert serialize_match_snapshot(state)['cards'][bolt_id] == proof['bolt_birth']
    assert state.spells_cast_this_turn == proof['cast_counts']
    tapped = [cid for cid in proof['forges'] if state.cards[cid].tapped]
    assert set(tapped) == {row['source']['card_id'] for row in contract['steps'][:index+1]}
    assert state.pending_replacement_choice['source_card_id'] == step['source']['card_id']
    assert state.pending_replacement_choice['target_player'] == seat
    assert state.players[seat].mana_pool == _expected_pool(proof, index + 1)
    assert sum(state.players[seat].mana_pool.values()) == index + 1
    assert state.players[3-seat].life == 20
    assert state.sideboard_facts == proof['stock'] and set(state.cards) == proof['cards']
    _assert_owner_private(state)


def _assert_published(state, proof, selected):
    seat, bolt_id = proof['seat'], proof['bolt']
    assert not state.pending_replacement_choice and not state.pending_mechanic_choice
    assert state.mana_continuation is None
    assert len(state.stack) == 1
    item = state.stack[0]
    bolt = state.cards[bolt_id]
    assert item.source_card_id == bolt_id and item.controller == seat
    assert item.label == 'Lightning Bolt' and item.effect_key == 'deal_damage'
    assert item.payload['__announced_stack_kind'] == 'spell'
    assert item.payload['target_player'] == 3-seat and item.payload['amount'] == 3
    assert item.payload['__announced_targets'] == {'target_player': 3-seat}
    # Player targets have no physical Card reference in the existing native ABI.
    assert item.payload['__announced_target_references'] == {'version': 1, 'targets': {}}
    assert item.payload['mana_spent'] == 1
    assert bolt.owner == bolt.controller == seat and bolt.zone == Zone.STACK
    assert bolt_id not in state.players[seat].hand
    assert bolt.zone_change_sequence == proof['hand_reference'][1] + 1
    assert object_incarnation(bolt) == proof['hand_reference'][0]
    assert bolt.printed_characteristics == proof['printed']
    assert state.spells_cast_this_turn == {
        **proof['cast_counts'], seat: proof['cast_counts'].get(seat, 0) + 1,
    }
    produced = len(proof['payment_contract']['steps'])
    assert sum(state.cards[cid].tapped for cid in proof['forges']) == produced
    assert state.players[seat].mana_pool == _expected_pool(proof, produced, spent=True)
    assert balances(state) == _expected_balances(proof, selected, produced)
    assert state.players[seat].prevent_damage_shield == 6 - produced
    assert state.players[seat].life == state.players[3-seat].life == 20
    assert state.sideboard_facts == proof['stock'] and set(state.cards) == proof['cards']
    _assert_owner_private(state)


def _complete_payment(state, proof, selected, roundtrip):
    seat = proof['seat']
    root = proof['native_root']
    assert fingerprint(root) == proof['native_root_fingerprint']
    control = act(root, seat, deepcopy(proof['cast_action']))
    receipt_id = list(proof['balances'])[selected]
    for index in range(len(proof['payment_contract']['steps'])):
        if roundtrip:
            state = _json_restore(state)
        _assert_paused(state, proof, selected, index)
        _assert_paused(control, proof, selected, index)
        _assert_same_native(state, control)
        before = fingerprint(state)
        with pytest.raises(ActionRejected):
            choose(state, 3-seat, receipt_id)
        assert fingerprint(state) == before
        _assert_paused(state, proof, selected, index)
        state = choose(state, seat, receipt_id)
        control = choose(control, seat, receipt_id)
        assert balances(state) == _expected_balances(proof, selected, index + 1)
        assert balances(control) == _expected_balances(proof, selected, index + 1)
        _assert_same_native(state, control)
    _assert_published(state, proof, selected)
    _assert_published(control, proof, selected)
    assert fingerprint(root) == proof['native_root_fingerprint']
    return state, control


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('selected', [0, 1])
@pytest.mark.parametrize('roundtrip', [False, True])
def test_targeted_bolt_keeps_owner_target_and_once_only_native_resolution(
        seat, selected, roundtrip):
    state, proof = _pause_targeted_bolt(seat)
    state, control = _complete_payment(state, proof, selected, roundtrip)
    _assert_published(state, proof, selected)
    published = deepcopy(serialize_match_snapshot(state)['stack'])
    if roundtrip:
        state = _json_restore(state)
        assert serialize_match_snapshot(state)['stack'] == published
    _assert_published(state, proof, selected)
    _assert_same_native(state, control)
    state = finish_stack(state)
    control = finish_stack(control)
    _assert_same_native(state, control)
    assert not state.stack and not state.pending_replacement_choice
    assert not state.pending_mechanic_choice and not state.pending_trigger_order
    assert state.players[3-seat].life == 17
    assert state.players[seat].life == 20
    produced = len(proof['payment_contract']['steps'])
    assert state.players[seat].prevent_damage_shield == 6 - produced
    assert balances(state) == _expected_balances(proof, selected, produced)
    assert state.players[seat].mana_pool == _expected_pool(proof, produced, spent=True)
    assert sum(state.cards[cid].tapped for cid in proof['forges']) == produced
    bolt = state.cards[proof['bolt']]
    assert bolt.owner == seat and bolt.zone == Zone.GRAVEYARD
    assert proof['bolt'] in state.players[seat].graveyard
    assert bolt.zone_change_sequence == proof['hand_reference'][1] + 2
    assert state.spells_cast_this_turn[seat] == proof['cast_counts'].get(seat, 0) + 1
    expected_stock = deepcopy(proof['stock'])
    source_id = proof['bolt']
    owner = expected_stock['inventory'][source_id]['owner']
    protected = expected_stock['seats'][str(owner)]['protected']
    if source_id not in protected:
        protected.append(source_id)
    assert state.sideboard_facts == expected_stock and set(state.cards) == proof['cards']
    assert state.winner is None
    _assert_owner_private(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('selected', [0, 1])
@pytest.mark.parametrize('roundtrip', [False, True])
def test_targeted_bolt_wrong_seat_and_replayed_receipt_are_atomic_and_private(
        seat, selected, roundtrip):
    state, proof = _pause_targeted_bolt(seat)
    state, control = _complete_payment(state, proof, selected, roundtrip)
    receipt_id = list(proof['balances'])[selected]
    _assert_published(state, proof, selected)
    if roundtrip:
        state = _json_restore(state)
    before = fingerprint(state)
    with pytest.raises(ActionRejected):
        choose(state, seat, receipt_id)
    assert fingerprint(state) == before
    _assert_published(state, proof, selected)
    _assert_same_native(state, control)
