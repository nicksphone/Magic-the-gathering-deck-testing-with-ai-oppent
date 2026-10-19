"""Canonical zero/power/replacement boundaries for the shared quantity compiler."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.continuous import effective_power
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import _token_base_quantity, infer_effect_from_oracle
from rules_engine.oracle_text import without_reminder_text
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_dynamic_death_quantity import (FAMILIES, add, cards, pay_with_events,
                                             position, restart, tokens, write_receipt)


DIRECTORY = Path(__file__).parent / 'fixtures/dynamic_death_quantity_boundaries'
RAW = json.loads((DIRECTORY / 'canonical.json').read_text())
cards.ROWS.update(RAW)


def test_boundary_canonical_provenance():
    pin = json.loads((DIRECTORY / 'provenance.json').read_text())
    assert pin['http_requests'] == 0 and not pin['facts_modified']
    assert pin['source_records_verified'] == 38690
    assert hashlib.sha256((DIRECTORY / 'canonical.json').read_bytes()).hexdigest() == pin['canonical_json_sha256']
    for name, row in RAW.items():
        expected = pin['rows'][name]
        assert row['id'] == expected['id'] and row['oracle_id'] == expected['oracle_id']
        encoded = json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        assert hashlib.sha256(encoded).hexdigest() == expected['raw_canonical_sha256']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Hangarback Walker', 'Hooded Hydra', 'Chasm Skulker'])
@pytest.mark.parametrize('count', [0, 2])
def test_literal_counter_zero_and_other_counter_not_counted(request, monkeypatch, seat, name, count):
    state, source, action = position(seat, name, count)
    add(state, 'Glorious Anthem', seat)
    source.counters['charge'] = 7
    paid, events = pay_with_events(state, source, action, seat, monkeypatch)
    trigger = asdict(paid.stack[0])
    assert trigger['payload']['amount'] == count
    assert trigger['payload']['__source_lki']['counters']['charge'] == 7
    paid = restart(paid)
    assert resolve_top_of_stack(paid)
    generated = tokens(paid, seat)
    write_receipt(request, {'events': events, 'trigger': trigger,
                           'expected': count, 'actual': len(generated)})
    assert len(generated) == count


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('starting_counters,expected_power', [(0, -2), (2, 0)])
def test_actual_bewilder_negative_and_zero_power_create_zero(request, monkeypatch, seat, starting_counters, expected_power):
    state, source, action = position(seat, 'Nested Shambler', 1)
    source.counters['+1/+1'] = starting_counters
    spell = add(state, 'Bewilder', seat, Zone.HAND)
    add(state, 'Raging Goblin', seat, Zone.LIBRARY)
    state.players[seat].mana_pool = {'C': 2, 'U': 1}
    cast = {'type': 'cast_spell', 'card_id': spell.id, 'targets': {'target_card_id': source.id}}
    with cards.unchanged_root(state):
        cast_state = checked_action(state, RulesEngine(), seat, cast)
    assert resolve_top_of_stack(cast_state)
    assert effective_power(cast_state, source.id) == expected_power
    paid, events = pay_with_events(cast_state, cast_state.cards[source.id], action, seat, monkeypatch)
    trigger = asdict(paid.stack[0])
    assert trigger['payload']['__source_lki']['power'] == expected_power
    assert trigger['payload']['amount'] == 0
    paid = restart(paid)
    assert resolve_top_of_stack(paid)
    write_receipt(request, {'cast': cast, 'events': events, 'trigger': trigger,
                           'expected': 0, 'actual': len(tokens(paid, seat))})
    assert not tokens(paid, seat)


@pytest.mark.parametrize('seat', [1, 2])
def test_effective_power_includes_canonical_anthem(request, monkeypatch, seat):
    state, source, action = position(seat, 'Nested Shambler', 2)
    add(state, 'Glorious Anthem', seat)
    assert effective_power(state, source.id) == 3
    paid, events = pay_with_events(state, source, action, seat, monkeypatch)
    trigger = asdict(paid.stack[0])
    assert trigger['payload']['amount'] == 3
    assert resolve_top_of_stack(paid)
    generated = tokens(paid, seat)
    write_receipt(request, {'events': events, 'trigger': trigger, 'actual': len(generated)})
    assert len(generated) == 3 and all(card.tapped for card in generated)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_parallel_lives_replaces_count_once_after_base_compilation(request, monkeypatch, seat, name):
    state, source, action = position(seat, name, 2)
    add(state, 'Parallel Lives', seat)
    paid, events = pay_with_events(state, source, action, seat, monkeypatch)
    trigger = asdict(paid.stack[0])
    assert trigger['payload']['amount'] == 2
    paid = restart(paid)
    assert resolve_top_of_stack(paid)
    write_receipt(request, {'events': events, 'trigger': trigger,
                           'expected': 4, 'actual': len(tokens(paid, seat))})
    assert len(tokens(paid, seat)) == 4


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_foreign_owned_source_uses_death_controller_for_tokens(request, monkeypatch, seat, name):
    state, source, action = position(seat, name, 2)
    source.owner = 3 - seat
    paid, events = pay_with_events(state, source, action, seat, monkeypatch)
    assert source.id in paid.players[3 - seat].graveyard
    trigger = asdict(paid.stack[0])
    assert trigger['controller'] == trigger['payload']['__source_lki']['controller'] == seat
    assert resolve_top_of_stack(paid)
    generated = tokens(paid, seat)
    write_receipt(request, {'events': events, 'trigger': trigger,
                           'tokens': [asdict(card) for card in generated]})
    assert len(generated) == 2
    assert all(card.owner == card.controller == seat for card in generated)
    assert not tokens(paid, 3 - seat)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_dress_down_suppresses_self_death_quantity_trigger(request, monkeypatch, seat, name):
    state, source, action = position(seat, name, 2)
    add(state, 'Dress Down', seat)
    paid, events = pay_with_events(state, source, action, seat, monkeypatch)
    assert paid.cards[source.id].last_known_battlefield['printed_abilities_suppressed']
    assert not paid.stack and not tokens(paid, seat)
    write_receipt(request, {'events': events, 'lki': paid.cards[source.id].last_known_battlefield})


@pytest.mark.parametrize('seat', [1, 2])
def test_frozen_lki_is_not_nested_dictionary_alias(request, monkeypatch, seat):
    state, source, action = position(seat, 'Hangarback Walker', 2)
    paid, events = pay_with_events(state, source, action, seat, monkeypatch)
    receipt = deepcopy(paid.stack[0].payload['__source_lki'])
    paid.cards[source.id].last_known_battlefield['counters']['+1/+1'] = 99
    assert paid.stack[0].payload['__source_lki'] == receipt
    paid = restart(paid)
    assert resolve_top_of_stack(paid)
    write_receipt(request, {'events': events, 'frozen_lki': receipt, 'actual': len(tokens(paid, seat))})
    assert len(tokens(paid, seat)) == 2


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('count', [0, 3])
def test_announced_x_spell_remains_distinct_from_departure_context(request, seat, count):
    state = cards.position(seat)
    spell = add(state, 'Secure the Wastes', seat, Zone.HAND)
    state.players[seat].mana_pool = {'W': 1, 'C': count}
    action = {'type': 'cast_spell', 'card_id': spell.id, 'targets': {'x_value': count}}
    with cards.unchanged_root(state):
        paid = checked_action(state, RulesEngine(), seat, action)
    assert paid.stack[0].payload['amount'] == count
    assert '__source_lki' not in paid.stack[0].payload
    paid = restart(paid)
    assert resolve_top_of_stack(paid)
    write_receipt(request, {'action': action, 'expected': count, 'actual': len(tokens(paid, seat))})
    assert len(tokens(paid, seat)) == count


@pytest.mark.parametrize('name', ['Hornet Nest', 'Izoni, Thousand-Eyed'])
def test_unknown_canonical_quantity_not_guessed_from_x_or_unrelated_lki(name):
    oracle = without_reminder_text(RAW[name]['oracle_text']).lower()
    assert _token_base_quantity(oracle, {'x_value': 8, '__source_lki': {'power': 8, 'counters': {'+1/+1': 8}}}, 8) is None


@pytest.mark.parametrize('name', FAMILIES)
def test_source_dynamic_quantity_requires_receipt_not_announced_x(name):
    oracle = without_reminder_text(cards.ROWS[name]['oracle_text']).lower()
    death = next(line for line in oracle.splitlines() if 'dies, create' in line)
    assert _token_base_quantity(death.strip(' .'), {'x_value': 99}, 99) is None


def test_unknown_that_many_canonical_body_is_noop_with_warning():
    state = cards.position(1)
    source = add(state, 'Hornet Nest', 1)
    key, _ = infer_effect_from_oracle(state, source, 1)
    assert key == 'noop'
    assert any('Unsupported token base quantity' in line for line in state.log)
    assert not tokens(state, 1)
