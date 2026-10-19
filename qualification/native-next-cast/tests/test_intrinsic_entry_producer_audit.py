"""Frozen source audit: observed legal subset versus missing selectable identity."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.test_graveyard_self_activation_product import position, FAMILIES, raw_card, act, resolve, snapshot
from tests.test_resident_entry_counter_provider import (
    BALLISTA, RENATA, SEASON, resident, finish_choices)

HERE = Path(__file__).resolve().parents[1]
HANGARBACK_BYTES = (HERE / 'fixtures/hangarback-walker.json').read_bytes()
HANGARBACK = json.loads(HANGARBACK_BYTES)
PROVENANCE = json.loads((HERE / 'fixtures/hangarback-provenance.json').read_text())
CARDS = {'Walking Ballista': BALLISTA, 'Hangarback Walker': HANGARBACK}
CR = (HERE / 'fixtures/MagicCompRules-20260925.txt').read_text()


def record(request, **data):
    path = Path(os.environ['MTG_INTRINSIC_EVIDENCE']) / (
        hashlib.sha256(request.node.nodeid.encode()).hexdigest() + '.json')
    with path.open('x') as stream:
        json.dump({'node': request.node.nodeid, **data}, stream, indent=2, sort_keys=True)


def announced(seat, family, season):
    state, _ = position(seat, FAMILIES[0])
    provider = resident(state, RENATA, seat)
    if season:
        resident(state, SEASON, seat)
    card = raw_card(state, CARDS[family], seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 4}
    state.replacement_choice_players = {seat}
    original = snapshot(state)
    state = act(state, seat, {'type': 'cast_spell', 'card_id': card.id,
                              'targets': {'x_value': 2}})
    assert not any(state.players[seat].mana_pool.values())
    assert state.cards[card.id].zone == Zone.STACK
    assert state.stack[-1].payload['x_value'] == 2
    return state, card.id, provider.id, original


def test_existing_full_canonical_and_official_rules_pins():
    assert hashlib.sha256(HANGARBACK_BYTES.rstrip(b'\n')).hexdigest() == PROVENANCE['canonical_record_sha256']
    assert HANGARBACK['id'] == PROVENANCE['id'] and HANGARBACK['oracle_id'] == PROVENANCE['oracle_id']
    assert PROVENANCE['source_sha256'] == '17cf0c4d0c96dde18337326626037732d0ff219c498d19ef0c9536f6db62dc13'
    assert not PROVENANCE['facts_modified'] and PROVENANCE['http_requests'] == 0
    assert hashlib.sha256((HERE / 'fixtures/MagicCompRules-20260925.txt').read_bytes()).hexdigest() == (
        '8d860e451f20f38865b725b42d82feb714c725373dd8f3b32b8652b3eeb070ca')


@pytest.mark.parametrize('family', CARDS)
def test_clause_and_rules_require_an_intrinsic_entry_identity_not_self_replacement_priority(family):
    assert CARDS[family]['oracle_text'].splitlines()[0] == 'This creature enters with X +1/+1 counters on it.'
    assert CARDS[family]['mana_cost'] == '{X}{X}'
    # Source-backed requirements only; this is not an executable rules model.
    for number in ('113.6h', '614.1c', '614.5', '614.12', '614.15',
                   '614.16', '616.1a', '616.1e', '616.1f', '616.1g', '616.2'):
        assert '\n' + number + ' ' in CR or '\n' + number + '. ' in CR
    assert 'an effect of a resolving spell or ability that replace part or all' in CR
    # The intrinsic static instruction is not an effect replacing its own
    # resolving spell text (614.15); 616.1a does not force intrinsic-first here.
    assert 'instead' not in CARDS[family]['oracle_text'].splitlines()[0]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', CARDS)
@pytest.mark.parametrize('preference', ['add', 'double'])
def test_actual_paid_observed_subset_preserves_root_rng_and_native_restore(request, seat, family, preference):
    state, cid, provider, original = announced(seat, family, True)
    state = resolve(state)
    pending = deepcopy(state.pending_replacement_choice)
    assert pending and pending['player_id'] == seat
    assert state.cards[cid].zone == Zone.STACK
    assert pending['counter_payload']['amount'] == 2
    assert {option['name'] for option in pending['options']} == {RENATA, SEASON}
    assert cid not in {option['source_card_id'] for option in pending['options']}
    result, choices = finish_choices(state, preference)
    assert len(choices) == len(set(choices))
    assert result.cards[cid].zone == Zone.BATTLEFIELD
    observed = result.cards[cid].counters.get('+1/+1')
    # Known engine subset: implicit intrinsic-first, then add/double or
    # double/add. This does NOT certify all legal entry choices/outcomes.
    assert observed == (6 if preference == 'add' else 5)
    assert result.players[seat].battlefield.count(cid) == 1
    assert not any(result.players[seat].mana_pool.values())
    assert result.cards[cid].oracle_text == CARDS[family]['oracle_text']
    assert result.cards[cid].mana_cost == CARDS[family]['mana_cost']
    assert snapshot(deserialize_match_snapshot(snapshot(result))) == snapshot(result)
    record(request, scope='observed intrinsic-first subset, not exhaustive entry ordering',
           before=original, pending=pending, after=snapshot(result), choices=choices,
           observed_counters=observed, intrinsic_identity_offered=False,
           rules_constraints={'initial_entry_producers': ['intrinsic', 'resident'],
               'counter_modifier_requires_positive_counter_event': True,
               'intrinsic_static_is_not_priority_self_replacement': True})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', CARDS)
@pytest.mark.parametrize('season', [False, True])
def test_strict_desired_initial_choice_offers_intrinsic_and_resident_entry_producers(request, seat, family, season):
    state, cid, provider, original = announced(seat, family, season)
    state = resolve(state)
    pending = state.pending_replacement_choice
    record(request, scope='strict desired identity, independent of final numeric outcome',
           before=original, observed=snapshot(state), pending=pending,
           expected_source_card_ids=[cid, provider], expected_pre_counter_amount=0)
    # This is the genuine missing seam; do not fake a pending packet or
    # execute a made-up intrinsic choice, skip, xfail, or relax this assertion.
    assert pending is not None, 'Both real entry producers must be selectable before aggregation'
    assert state.cards[cid].zone == Zone.STACK
    offered = {option['source_card_id'] for option in pending['options']}
    assert {cid, provider} <= offered, 'Intrinsic entry replacement identity missing'
    assert pending['counter_payload']['amount'] == 0, 'Entry counters were pre-aggregated before choice'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', CARDS)
def test_unfunded_actual_x_two_cast_rejected_atomically(seat, family):
    state, _ = position(seat, FAMILIES[0])
    resident(state, RENATA, seat)
    card = raw_card(state, CARDS[family], seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 3}
    before = snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {
            'type': 'cast_spell', 'card_id': card.id, 'targets': {'x_value': 2}})
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', CARDS)
def test_wrong_actor_existing_replacement_choice_preserves_root(seat, family):
    state, _, _, _ = announced(seat, family, True)
    state = resolve(state)
    pending = state.pending_replacement_choice
    before = snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-seat, {
            'type': 'choose_replacement', 'replacement_source_id': pending['options'][0]['source_id']})
    assert snapshot(state) == before
