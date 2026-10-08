"""Desired complete-body paid goldens. Current unsupported casts must be RED."""
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

import inventory as inv
import domain_paid_support as g
import test_march_current_baseline as current
from game_state.state import Zone, object_incarnation
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import ActionRejected
from rules_engine.mana import mana_value
from rules_engine.oracle_effects import inspect_target_hints

OUT = inv.ROOT.parent / 'evidence'
PHASE = os.environ['ADMISSION_PHASE']
MARCH = 'March of Otherworldly Light'


@pytest.fixture(scope='module')
def facts():
    seed, selected, proof = inv.load_inputs()
    raws = {name: selected[card['scryfall_id']] for name, card in seed.items()}
    assert raws[MARCH]['id'] == seed[MARCH]['scryfall_id']
    assert raws[MARCH]['oracle_text'] == seed[MARCH]['oracle_text']
    auxiliary = inv.ROOT / 'backend/tests/fixtures/cloudshift_compound_audit'
    for line in (auxiliary / 'SHA256SUMS').read_text().splitlines():
        digest, filename = line.split()
        assert inv.sha(auxiliary / Path(filename).name) == digest
    blink = json.loads((auxiliary / 'flicker-of-fate.json').read_bytes())
    assert blink['object'] == 'card' and blink['name'] == 'Flicker of Fate' and blink['oracle_id']
    raws[blink['name']] = blink
    with (OUT / ('march-desired-facts-' + PHASE + '.json')).open('x') as stream:
        json.dump({'source': proof, 'march': raws[MARCH],
                   'responses': {name: raws[name] for name in
                                 ['Counterspell', 'Otawara, Soaring City', 'Flicker of Fate']},
                   'auxiliary_fixture_sha256': inv.sha(auxiliary / 'flicker-of-fate.json')}, stream, indent=2)
    return raws


def cold(state, tmp_path, label):
    packet = serialize_match_snapshot(state)
    path = tmp_path / (label + '.json')
    path.write_text(json.dumps(packet))
    restored = deserialize_match_snapshot(json.loads(path.read_bytes()))
    assert serialize_match_snapshot(restored) == packet
    return restored


def receipt(label, facts, state, **observations):
    with (OUT / (PHASE + '-' + label + '.json')).open('x') as stream:
        json.dump({'canonical_march_sha256': inv.canonical_hash(facts[MARCH]),
                   'snapshot': serialize_match_snapshot(state),
                   'observations': observations}, stream, indent=2, sort_keys=True)


def prepare(facts, seat, x_value, target_type):
    state = g.position(facts, seat)
    if x_value == 0 and target_type == 'artifact':
        state, target = current.zero_artifact_from_paid_sunfall(state, facts, seat)
    else:
        name = ({'artifact': "Witch's Oven", 'creature': 'Dryad Arbor', 'enchantment': "Urza's Saga"}
                if x_value == 0 else
                {'artifact': "Witch's Oven", 'creature': 'Monastery Swiftspear', 'enchantment': 'Intangible Virtue'})[target_type]
        target = g.add(state, facts, name, 3-seat)
    assert mana_value(state.cards[target].mana_cost) <= x_value
    source = g.add(state, facts, MARCH, seat, Zone.HAND)
    white = g.add(state, facts, 'Leyline Binding', seat, Zone.HAND)
    nonwhite = g.add(state, facts, 'Searing Blaze', seat, Zone.HAND)
    state = g.respond(state, seat)
    state.players[seat].mana_pool = {'C': x_value, 'W': 1}
    return state, source, target, [white, nonwhite]


def paid_march(state, seat, source, target, x_value):
    # ONLY current public fields. No hypothetical pitch field or forced legal move.
    paid = g.act(state, seat, 'cast_spell', card_id=source, cost_choice={'id': 'base'},
                 targets={'x_value': x_value, 'target_card_id': target})
    assert sum(paid.players[seat].mana_pool.values()) == 0
    assert paid.cards[source].zone == Zone.STACK
    item = paid.stack[-1]
    from rules_engine.targeting import stack_object_kind
    assert item.source_card_id == source and item.controller == seat
    assert stack_object_kind(paid, item) == 'spell'
    assert item.payload['__announced_targets'] == {'x_value': x_value, 'target_card_id': target}
    return paid


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('x_value', [0, 2, 4])
@pytest.mark.parametrize('target_type', ['artifact', 'creature', 'enchantment'])
def test_desired_actual_paid_zero_optional_march_exiles_valid_target(facts, seat, x_value, target_type, tmp_path):
    state, source, target, retained = prepare(facts, seat, x_value, target_type)
    before = serialize_match_snapshot(state)
    target_owner = state.cards[target].owner
    state = paid_march(cold(state, tmp_path, 'before-payment'), seat, source, target, x_value)
    assert serialize_match_snapshot(state) != before
    assert all(state.cards[cid].zone == Zone.HAND for cid in retained)
    state = cold(state, tmp_path, 'paid-stack')
    g.resolve(state)
    assert state.cards[source].zone == Zone.GRAVEYARD
    if state.cards[target].is_token:
        assert state.cards[target].zone == Zone.CEASED
        assert f'{state.cards[target].name} is exiled.' in state.log
    else:
        assert target in state.players[target_owner].exile and state.cards[target].zone == Zone.EXILE
    assert all(state.cards[cid].zone == Zone.HAND for cid in retained)
    assert not state.stack
    state = cold(state, tmp_path, 'resolved')
    receipt(f'paid-{seat}-{x_value}-{target_type}', facts, state,
            paid_generic=x_value, paid_W=1, optional_exiles=0, target_owner=target_owner,
            source_after='graveyard', committed_exile=True,
            target_after=state.cards[target].zone.value, serialized_restore=True)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('response', ['counterspell', 'bounce', 'blink'])
def test_desired_paid_march_real_response_and_serialized_restore(facts, seat, response, tmp_path):
    state, source, target, retained = prepare(
        facts, seat, 2, 'enchantment' if response == 'blink' else 'artifact')
    state = paid_march(state, seat, source, target, 2)
    announced_incarnation = object_incarnation(state.cards[target])
    state = g.respond(cold(state, tmp_path, 'march-paid'), 3-seat)
    if response == 'counterspell':
        responder = g.add(state, facts, 'Counterspell', 3-seat, Zone.HAND)
        state.players[3-seat].mana_pool = {'U': 2}
        state = g.cast(state, 3-seat, responder, target_stack_id=state.stack[-1].id)
    elif response == 'bounce':
        responder = g.add(state, facts, 'Otawara, Soaring City', 3-seat, Zone.HAND)
        state.players[3-seat].mana_pool = {'C': 3, 'U': 1}
        state = g.act(state, 3-seat, 'activate_ability', card_id=responder, ability_index=1,
                      targets={'target_card_id': target})
    else:
        responder = g.add(state, facts, 'Flicker of Fate', 3-seat, Zone.HAND)
        state.players[3-seat].mana_pool = {'C': 1, 'W': 1}
        state = g.cast(state, 3-seat, responder, target_card_id=target)
    assert sum(state.players[3-seat].mana_pool.values()) == 0
    state = cold(state, tmp_path, 'response-paid')
    g.resolve(state)
    assert state.cards[responder].zone == Zone.GRAVEYARD
    if response == 'counterspell':
        assert not state.stack and state.cards[target].zone == Zone.BATTLEFIELD
    else:
        assert len(state.stack) == 1 and state.stack[-1].source_card_id == source
        if response == 'bounce':
            assert state.cards[target].zone == Zone.HAND
        else:
            assert state.cards[target].zone == Zone.BATTLEFIELD
            assert object_incarnation(state.cards[target]) != announced_incarnation
        state = cold(state, tmp_path, 'before-original-resolution')
        g.resolve(state)
        assert state.cards[target].zone == (Zone.HAND if response == 'bounce' else Zone.BATTLEFIELD)
    assert state.cards[source].zone == Zone.GRAVEYARD and not state.stack
    assert all(state.cards[cid].zone == Zone.HAND for cid in retained)
    receipt(f'response-{seat}-{response}', facts, cold(state, tmp_path, 'response-finished'),
            march_paid_generic=2, march_paid_W=1, optional_exiles=0,
            response=response, target_original_incarnation=announced_incarnation,
            target_after=state.cards[target].zone.value, serialized_restore=True)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('x_value', [0, 2, 4])
def test_desired_above_x_rejected_only_after_successful_paid_control(facts, seat, x_value, tmp_path):
    state, source, target, retained = prepare(facts, seat, x_value, 'creature')
    above = g.add(state, facts, 'Torrential Gearhulk', 3-seat)
    assert mana_value(state.cards[above].mana_cost) == 6 > x_value
    # A cost-blocked implementation cannot make this target-negative green.
    control = paid_march(deepcopy(state), seat, source, target, x_value)
    control = cold(control, tmp_path, 'successful-control')
    g.resolve(control)
    assert control.cards[source].zone == Zone.GRAVEYARD
    assert control.cards[target].zone == Zone.EXILE
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        g.act(state, seat, 'cast_spell', card_id=source, cost_choice={'id': 'base'},
              targets={'x_value': x_value, 'target_card_id': above})
    assert serialize_match_snapshot(state) == before
    assert all(state.cards[cid].zone == Zone.HAND for cid in retained)
    receipt(f'above-x-{seat}-{x_value}', facts, state,
            paid_positive_control=True, above_target_mv=6, selected_x=x_value,
            invalid_target_root_unchanged=True)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('x_value', [0, 2, 4])
def test_desired_fullbody_announced_x_hint_cap(facts, seat, x_value):
    state, source, target, retained = prepare(facts, seat, x_value, 'creature')
    artifact_creature = g.add(state, facts, 'Torrential Gearhulk', 3-seat)
    enchantment = g.add(state, facts, 'Leyline Binding', 3-seat)
    before = serialize_match_snapshot(state)
    hints = inspect_target_hints(state, state.cards[source], seat, {'x_value': x_value})
    ids = {row['id'] for key, rows in hints.items() if key.endswith('_targets') and isinstance(rows, list)
           for row in rows if isinstance(row, dict) and 'id' in row}
    assert target in ids
    assert artifact_creature not in ids and enchantment not in ids
    assert serialize_match_snapshot(state) == before
