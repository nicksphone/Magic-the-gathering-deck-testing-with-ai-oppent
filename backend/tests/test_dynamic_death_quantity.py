"""Strict canonical quantities, with event/context receipts before assertions."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path

import pytest

from game_state.serializers import (deserialize_match_snapshot, serialize_card_view,
                                    serialize_match_snapshot)
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.continuous import effective_power
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.engine import RulesEngine
from rules_engine.mana_abilities import mana_ability_specs
from rules_engine.stack_engine import resolve_top_of_stack
from tests import test_spell_cost_overlap_investigation as cards


DIRECTORY = Path(__file__).parent / 'fixtures/dynamic_death_quantity'
RAW = json.loads((DIRECTORY / 'canonical.json').read_text())
cards.ROWS.update(RAW)
FAMILIES = ['Hangarback Walker', 'Hooded Hydra', 'Nested Shambler']


def add(state, name, seat, zone=Zone.BATTLEFIELD):
    card = cards.add(state, name, seat, zone)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
    return card


def position(seat, name, count=2, exile=False):
    state = cards.position(seat)
    tower = add(state, 'Phyrexian Tower', seat)
    source = add(state, name, seat)
    counters = count - 1 if name == 'Nested Shambler' else count
    if name != 'Reef Worm':
        source.counters['+1/+1'] = counters
    if exile:
        add(state, 'Rest in Peace', seat)
    spec = next(spec for spec in mana_ability_specs(tower, state) if 'Sacrifice' in spec[1])
    action = {'type': 'activate_mana_ability', 'card_id': tower.id,
              'ability_index': spec[0], 'color': 'B',
              'payment_choices': {'sacrifice_card_ids': [source.id]}}
    return state, source, action


def write_receipt(request, receipt):
    directory = os.environ.get('MTG_DEATH_QUANTITY_EVIDENCE')
    if directory:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
        (path / (key + '.json')).write_text(
            json.dumps({'test': request.node.nodeid, **receipt}, indent=2, sort_keys=True) + '\n')


def tokens(state, seat):
    return [state.cards[cid] for cid in state.players[seat].battlefield
            if state.cards[cid].is_token]


def public_status(state, source):
    with cards.unchanged_root(state):
        return {'known_unsupported': known_unsupported_mechanics(
                    source.oracle_text, card_name=source.name),
                'card_view': serialize_card_view(state, source.id)}


def pay_with_events(state, source, action, seat, monkeypatch):
    import rules_engine.events as events
    observed = []
    original = events.emit_event_batch
    original_parse = events._trigger_from_oracle

    def observe(current, event, payloads):
        if any(payload.get('card_id') == source.id for payload in payloads):
            observed.append({'event': event, 'payloads': deepcopy(payloads),
                             'source_lki': deepcopy(current.cards[source.id].last_known_battlefield),
                             'source_counters': dict(current.cards[source.id].counters)})
        return original(current, event, payloads)

    def observe_parse(current, source_id, controller, oracle, **kwargs):
        result = original_parse(current, source_id, controller, oracle, **kwargs)
        if source_id == source.id:
            observed.append({'event': 'trigger_parse', 'input': deepcopy(kwargs),
                             'source_lki': deepcopy(current.cards[source_id].last_known_battlefield),
                             'output': deepcopy(result)})
        return result

    with monkeypatch.context() as patch:
        patch.setattr(events, 'emit_event_batch', observe)
        patch.setattr(events, '_trigger_from_oracle', observe_parse)
        with cards.unchanged_root(state):
            paid = checked_action(state, RulesEngine(), seat, action)
    return paid, observed


def restart(state):
    snapshot = serialize_match_snapshot(state)
    result = deserialize_match_snapshot(json.loads(json.dumps(snapshot)))
    assert serialize_match_snapshot(result) == snapshot
    return result


def test_canonical_provenance():
    provenance = json.loads((DIRECTORY / 'provenance.json').read_text())
    assert provenance['source_records_verified'] == 38690
    assert provenance['http_requests'] == 0 and not provenance['facts_modified']
    assert hashlib.sha256((DIRECTORY / 'canonical.json').read_bytes()).hexdigest() == provenance['canonical_json_sha256']
    for name, pin in provenance['rows'].items():
        row = RAW[name]
        assert row['id'] == pin['id'] and row['oracle_id'] == pin['oracle_id']
        encoded = json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        assert hashlib.sha256(encoded).hexdigest() == pin['raw_canonical_sha256']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_correct_departure_context_reaches_trigger_parser(request, monkeypatch, seat, name):
    state, source, action = position(seat, name, 3)
    old_incarnation = source.battlefield_incarnation
    expected_power = effective_power(state, source.id)
    paid, events = pay_with_events(state, source, action, seat, monkeypatch)
    parsed = next(row for row in events if row['event'] == 'trigger_parse')
    assert parsed['input']['event'] == 'creature_dies'
    assert parsed['input']['payload']['card_id'] == source.id
    assert parsed['input']['payload']['power'] == expected_power == 3
    assert parsed['source_lki']['battlefield_incarnation'] == old_incarnation
    assert parsed['source_lki']['counters'] == source.counters
    assert paid.players[seat].mana_pool['B'] == 2
    assert paid.cards[source.id].zone == Zone.GRAVEYARD
    write_receipt(request, {'events': events, 'queued': serialize_match_snapshot(paid)})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('count', [2, 3])
@pytest.mark.parametrize('resume', [False, True])
def test_dynamic_self_death_exact_quantity(request, monkeypatch, seat, name, count, resume):
    state, source, action = position(seat, name, count)
    before = serialize_match_snapshot(state)
    status = public_status(state, source)
    incarnation = source.battlefield_incarnation
    power = effective_power(state, source.id)
    paid, events = pay_with_events(state, source, action, seat, monkeypatch)
    lki = deepcopy(paid.cards[source.id].last_known_battlefield)
    assert lki['battlefield_incarnation'] == incarnation
    assert lki['power'] == power
    assert lki['counters']['+1/+1'] == source.counters['+1/+1']
    assert paid.cards[source.id].counters == {}
    assert len(paid.stack) == 1 and paid.stack[0].source_card_id == source.id
    trigger = asdict(paid.stack[0])
    if resume:
        paid = restart(paid)
    assert resolve_top_of_stack(paid)
    generated = tokens(paid, seat)
    write_receipt(request, {'setup': before, 'action': action, 'status': status,
                           'events': events, 'lki': lki, 'trigger': trigger,
                           'resumed': resume, 'expected': count, 'actual': len(generated),
                           'tokens': [asdict(card) for card in generated],
                           'resolved': serialize_match_snapshot(paid)})
    assert len(generated) == count, f'{name}: expected {count}, actual {len(generated)}'
    if name == 'Nested Shambler':
        assert all(card.tapped for card in generated)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_old_trigger_uses_departed_not_returned_incarnation(request, monkeypatch, seat, name):
    state, source, action = position(seat, name, 2)
    paid, events = pay_with_events(state, source, action, seat, monkeypatch)
    old_lki = deepcopy(paid.cards[source.id].last_known_battlefield)
    old_trigger = asdict(paid.stack[0])
    returned = paid.cards[source.id]
    paid.players[returned.owner].graveyard.remove(returned.id)
    returned.move_to_zone(Zone.HAND)
    returned.move_to_zone(Zone.BATTLEFIELD)
    paid.players[seat].battlefield.append(returned.id)
    assign_static_order_on_battlefield_entry(paid, returned.id)
    returned.counters['+1/+1'] = 9
    assert returned.battlefield_incarnation != old_lki['battlefield_incarnation']
    assert asdict(paid.stack[0]) == old_trigger
    paid = restart(paid)
    assert resolve_top_of_stack(paid)
    generated = tokens(paid, seat)
    write_receipt(request, {'events': events, 'old_lki': old_lki,
                           'old_trigger': old_trigger, 'returned': asdict(returned),
                           'expected': 2, 'actual': len(generated),
                           'resolved': serialize_match_snapshot(paid)})
    assert len(generated) == 2


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_two_deaths_same_card_id_keep_separate_quantity_contexts(request, monkeypatch, seat, name):
    state, source, action = position(seat, name, 2)
    paid, first_events = pay_with_events(state, source, action, seat, monkeypatch)
    first_lki = deepcopy(paid.cards[source.id].last_known_battlefield)
    first_trigger = asdict(paid.stack[0])
    returned = paid.cards[source.id]
    paid.players[seat].graveyard.remove(returned.id)
    returned.move_to_zone(Zone.HAND)
    returned.move_to_zone(Zone.BATTLEFIELD)
    paid.players[seat].battlefield.append(returned.id)
    assign_static_order_on_battlefield_entry(paid, returned.id)
    returned.counters['+1/+1'] = 2 if name == 'Nested Shambler' else 3
    tower = add(paid, 'Phyrexian Tower', seat)
    action = {**action, 'card_id': tower.id}
    second, second_events = pay_with_events(paid, returned, action, seat, monkeypatch)
    second_lki = deepcopy(second.cards[source.id].last_known_battlefield)
    assert first_lki['battlefield_incarnation'] != second_lki['battlefield_incarnation']
    assert len(second.stack) == 2
    triggers = [asdict(item) for item in second.stack]
    second = restart(second)
    assert resolve_top_of_stack(second)
    first_resolved_count = len(tokens(second, seat))
    assert resolve_top_of_stack(second)
    final_count = len(tokens(second, seat))
    write_receipt(request, {'first_events': first_events, 'second_events': second_events,
                           'first_lki': first_lki, 'second_lki': second_lki,
                           'first_trigger_before_second_death': first_trigger,
                           'triggers': triggers, 'expected_newer': 3,
                           'actual_newer': first_resolved_count,
                           'expected_older': 2, 'actual_older': final_count - first_resolved_count,
                           'resolved': serialize_match_snapshot(second),
                           'setup_note': 'Helper-mediated return/reentry, not a public reanimation cast'})
    assert triggers[0]['payload'].get('__source_lki', {}).get('battlefield_incarnation') == first_lki['battlefield_incarnation']
    assert (first_resolved_count, final_count - first_resolved_count) == (3, 2)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_exile_replacement_emits_no_death_tokens(request, monkeypatch, seat, name):
    state, source, action = position(seat, name, exile=True)
    paid, events = pay_with_events(state, source, action, seat, monkeypatch)
    assert paid.cards[source.id].zone == Zone.EXILE
    assert not paid.stack and not tokens(paid, seat)
    assert not any(row['event'] in {'creature_dies', 'permanent_dies'} for row in events)
    resumed = restart(paid)
    assert not resumed.stack and not tokens(resumed, seat)
    write_receipt(request, {'events': events, 'resolved': serialize_match_snapshot(resumed)})


@pytest.mark.parametrize('seat', [1, 2])
def test_fixed_death_quantity_control(request, monkeypatch, seat):
    state, source, action = position(seat, 'Reef Worm')
    paid, events = pay_with_events(state, source, action, seat, monkeypatch)
    trigger = asdict(paid.stack[0])
    paid = restart(paid)
    assert resolve_top_of_stack(paid)
    generated = tokens(paid, seat)
    write_receipt(request, {'events': events, 'trigger': trigger,
                           'expected': 1, 'actual': len(generated),
                           'tokens': [asdict(card) for card in generated]})
    assert len(generated) == 1
    assert generated[0].power == generated[0].toughness == 3
