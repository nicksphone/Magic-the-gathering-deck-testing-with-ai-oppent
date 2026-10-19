"""Real Ward callbacks around modal target announcement, both seats."""
import json

import pytest
import inventory as inv
import test_suncleanser_desired as s
import test_paid_modal as m
from canonical_controls import load_controls
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.counter_placement import counter_placement_forbidden

facts = s.facts


@pytest.fixture(scope='module')
def ward_facts(facts):
    controls, proof = load_controls(['Tolarian Terror'])
    raw = controls['Tolarian Terror']
    assert 'Ward {2}' in raw['oracle_text']
    with (s.OUT / (s.PHASE + '-ward-facts.json')).open('x') as stream:
        json.dump({'source': proof, 'full_raw': raw, 'canonical_hash': s.digest(raw)}, stream, sort_keys=True, indent=2)
    return {**facts, raw['name']: raw}


def ward_choice(state, seat, pay):
    assert state.stack[-1].effect_key == 'ward_payment'
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice['kind'] == 'ward_payment'
    assert state.pending_mechanic_choice['player_id'] == seat
    option = 'pay' if pay else 'decline'
    assert option in state.pending_mechanic_choice['options']
    return s.g.act(s.cold(state), seat, 'choose_mechanic', card_ids=[option])


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('pay', [False, True])
def test_paid_modal_ward_callbacks(ward_facts, seat, pay):
    state = s.g.position(ward_facts, seat)
    target = s.g.add(state, ward_facts, 'Tolarian Terror', 3-seat)
    growth = s.g.add(state, ward_facts, 'Battlegrowth', seat, s.Zone.HAND)
    state.players[seat].mana_pool = {'G': 1, 'C': 2}
    state = s.g.cast(state, seat, growth, target_card_id=target)
    assert next(item for item in state.stack if item.source_card_id == growth).payload['mana_spent'] == 1
    state = ward_choice(state, seat, True)
    assert sum(state.players[seat].mana_pool.values()) == 0
    s.drain(state)
    assert state.cards[target].counters['+1/+1'] == 1
    state, source = m.source_entry(state, ward_facts, seat)
    state = m.select(state, seat, 'creature', target)
    assert state.cards[target].counters['+1/+1'] == 1
    state.players[seat].mana_pool = {'C': 2}
    state = ward_choice(state, seat, pay)
    s.drain(state)
    assert state.cards[source].zone == s.Zone.BATTLEFIELD
    assert state.cards[target].counters.get('+1/+1', 0) == (0 if pay else 1)
    assert counter_placement_forbidden(state, '+1/+1', target_card_id=target) == pay
    assert len(state.retained_counter_prohibitions) == int(pay)
    assert sum(state.players[seat].mana_pool.values()) == (0 if pay else 2)
    s.record('ward-' + str(seat) + '-' + str(pay), state, actual_pay_choice=pay, paid_generic=2 if pay else 0)
