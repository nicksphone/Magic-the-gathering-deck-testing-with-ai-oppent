"""Canonical ordering audit rebased onto the composed parent candidate."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.engine import RulesEngine
from rules_engine.events import emit_event
from rules_engine.mana_abilities import mana_ability_specs
from rules_engine.stack_engine import resolve_top_of_stack
from tests import test_spell_cost_overlap_investigation as cards


DIRECTORY = Path(__file__).parent / 'fixtures/death_cycle_ordering'
RAW = json.loads((DIRECTORY / 'canonical.json').read_text())
cards.ROWS.update(RAW)
MODES = ['none', 'rip', 'leyline_enemy', 'leyline_actor']


def add(state, name, seat, zone=Zone.BATTLEFIELD):
    card = cards.add(state, name, seat, zone)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
    return card


def replacement(state, seat, mode):
    if mode == 'rip':
        return add(state, 'Rest in Peace', seat)
    if mode.startswith('leyline'):
        return add(state, 'Leyline of the Void', 3 - seat if mode == 'leyline_enemy' else seat)
    return None


def destination(mode, seat, owner):
    return (Zone.EXILE if mode == 'rip' or
            mode == 'leyline_enemy' and owner == seat or
            mode == 'leyline_actor' and owner != seat else Zone.GRAVEYARD)


def tokens(state, seat):
    return [state.cards[cid] for cid in state.players[seat].battlefield if state.cards[cid].is_token]


def receipt(request, data):
    root = os.environ.get('MTG_ORDERING_AUDIT_EVIDENCE')
    if root:
        directory = Path(root)
        directory.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
        (directory / (key + '.json')).write_text(
            json.dumps({'test': request.node.nodeid, **data}, indent=2, sort_keys=True) + '\n')


def restart(state):
    snapshot = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(json.loads(json.dumps(snapshot)))
    assert serialize_match_snapshot(restored) == snapshot
    return restored


def observed_action(state, seat, source, action, monkeypatch):
    import rules_engine.events as events
    import rules_engine.engine as engine
    records = []
    single, batch = events.emit_event, events.emit_event_batch

    def observe(current, event, payloads, call):
        relevant = [payload for payload in payloads if payload.get('card_id') == source.id]
        if relevant:
            records.append({'event': event, 'payloads': deepcopy(relevant),
                            'zone_at_event': current.cards[source.id].zone,
                            'lki_at_event': deepcopy(current.cards[source.id].last_known_battlefield)})
        return call()

    with monkeypatch.context() as patch:
        patch.setattr(events, 'emit_event', lambda current, event, payload:
                      observe(current, event, [payload], lambda: single(current, event, payload)))
        patch.setattr(events, 'emit_event_batch', lambda current, event, payloads:
                      observe(current, event, payloads, lambda: batch(current, event, payloads)))
        patch.setattr(engine, 'emit_event', events.emit_event)
        patch.setattr(engine, 'emit_event_batch', events.emit_event_batch)
        with cards.unchanged_root(state):
            result = checked_action(state, RulesEngine(), seat, action)
    return result, records


def death_position(seat, name, mode='none', foreign_owner=False, suppress=False):
    state = cards.position(seat)
    source = add(state, name, seat)
    if foreign_owner:
        source.owner = 3 - seat
    source.counters['charge' if name == 'Chromatic Star' else '+1/+1'] = 2
    replacement(state, seat, mode)
    if suppress:
        add(state, 'Dress Down', seat)
    add(state, 'Raging Goblin', seat, Zone.LIBRARY)
    if name == 'Chromatic Star':
        state.players[seat].mana_pool = {'C': 1}
        mana_source = source
        color = 'U'
        payments = None
    else:
        mana_source = add(state, 'Phyrexian Tower', seat)
        color = 'B'
        payments = {'sacrifice_card_ids': [source.id]}
    spec = next(spec for spec in mana_ability_specs(mana_source, state) if 'Sacrifice' in spec[1])
    action = {'type': 'activate_mana_ability', 'card_id': mana_source.id,
              'ability_index': spec[0], 'color': color}
    if payments is not None:
        action['payment_choices'] = payments
    return state, source, action


def cycle_position(seat, name, mode='none'):
    state = cards.position(seat)
    source = add(state, name, seat, Zone.HAND)
    replacement(state, seat, mode)
    if mode == 'dress':
        add(state, 'Dress Down', seat)
    for card_name in ['Island', 'Forest', 'Raging Goblin']:
        add(state, card_name, seat, Zone.LIBRARY)
    state.players[seat].mana_pool = {'C': 3, 'U': 1, 'G': 1}
    action = {'type': 'cycle_card', 'card_id': source.id}
    if name == 'Shark Typhoon':
        action['x_value'] = 2
    return state, source, action


def test_canonical_raw_records_unchanged():
    pin = json.loads((DIRECTORY / 'provenance.json').read_text())
    assert pin['source_records_verified'] == 38690 and pin['http_requests'] == 0
    assert not pin['facts_modified']
    assert hashlib.sha256((DIRECTORY / 'canonical.json').read_bytes()).hexdigest() == pin['canonical_json_sha256']
    for name, expected in pin['rows'].items():
        row = RAW[name]
        assert row['id'] == expected['id'] and row['oracle_id'] == expected['oracle_id']
        encoded = json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        assert hashlib.sha256(encoded).hexdigest() == expected['raw_canonical_sha256']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Chromatic Star', 'Heartfire Hero', 'Reef Worm'])
@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('foreign_owner', [False, True])
def test_card_death_replacement_before_self_trigger_and_counter_reset(request, monkeypatch, seat, name, mode, foreign_owner):
    state, source, action = death_position(seat, name, mode, foreign_owner)
    before = serialize_match_snapshot(state)
    expected = destination(mode, seat, source.owner)
    paid, events = observed_action(state, seat, source, action, monkeypatch)
    queued = [asdict(item) for item in paid.stack]
    lki = deepcopy(paid.cards[source.id].last_known_battlefield)
    paid = restart(paid)
    for _ in range(3):
        if not paid.stack:
            break
        assert resolve_top_of_stack(paid)
    receipt(request, {'setup': before, 'action': action, 'events': events,
                      'queued': queued, 'lki': lki, 'expected_destination': expected,
                      'resolved': serialize_match_snapshot(paid)})
    assert paid.cards[source.id].zone == expected
    assert source.id in getattr(paid.players[source.owner], expected.value)
    assert lki['battlefield_incarnation'] == source.battlefield_incarnation
    assert lki['counters'] == source.counters
    assert not paid.cards[source.id].counters
    order = [row['event'] for row in events]
    assert order.index('leaves_battlefield') < order.index('sacrifice')
    if expected == Zone.EXILE:
        assert not queued and not tokens(paid, seat)
        assert len(paid.players[seat].hand) == 0
        assert paid.players[3 - seat].life == 20
        assert not any(row['event'] in {'creature_dies', 'permanent_dies'} for row in events)
    else:
        assert len(queued) == 1
        if name == 'Chromatic Star':
            assert len(paid.players[seat].hand) == 1
        elif name == 'Heartfire Hero':
            assert paid.players[3 - seat].life == 17
        else:
            assert len(tokens(paid, seat)) == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Chromatic Star', 'Heartfire Hero', 'Reef Worm'])
@pytest.mark.parametrize('mode', ['none', 'rip'])
def test_suppression_is_source_type_specific_not_blanket_death_rule(request, monkeypatch, seat, name, mode):
    state, source, action = death_position(seat, name, mode, suppress=True)
    paid, events = observed_action(state, seat, source, action, monkeypatch)
    expected_triggers = 1 if name == 'Chromatic Star' and mode == 'none' else 0
    receipt(request, {'events': events, 'queued': serialize_match_snapshot(paid),
                      'expected_triggers': expected_triggers})
    assert len(paid.stack) == expected_triggers
    assert paid.cards[source.id].last_known_battlefield['printed_abilities_suppressed'] == (name != 'Chromatic Star')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Shark Typhoon', 'Krosan Tusker'])
@pytest.mark.parametrize('mode', MODES + ['dress'])
def test_cycle_self_trigger_survives_discard_replacement_not_death(request, monkeypatch, seat, name, mode):
    state, source, action = cycle_position(seat, name, mode)
    paid, events = observed_action(state, seat, source, action, monkeypatch)
    expected = destination(mode, seat, source.owner)
    queued = [asdict(item) for item in paid.stack]
    receipt(request, {'setup': serialize_match_snapshot(state), 'action': action,
                      'events': events, 'queued': queued,
                      'status': known_unsupported_mechanics(source.oracle_text, card_name=name),
                      'resolved': serialize_match_snapshot(restart(paid)),
                      'baseline': 'Composed parent includes generic self-cycling matcher'})
    assert paid.cards[source.id].zone == expected
    assert [row['event'] for row in events] == ['discard', 'cycle']
    assert events[-1]['payloads'][0]['x_value'] == action.get('x_value', 0)
    assert not any(row['event'] in {'creature_dies', 'permanent_dies'} for row in events)
    assert len(queued) == 2
    assert queued[0]['effect_key'] == 'cycle_draw'
    assert queued[1]['source_card_id'] == source.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mode', MODES)
def test_plain_cycling_draw_still_resolves_after_exile_cost_destination(request, monkeypatch, seat, mode):
    state, source, action = cycle_position(seat, 'Lonely Sandbar', mode)
    paid, events = observed_action(state, seat, source, action, monkeypatch)
    assert len(paid.stack) == 1 and paid.stack[0].effect_key == 'cycle_draw'
    paid = restart(paid)
    assert resolve_top_of_stack(paid)
    receipt(request, {'events': events, 'resolved': serialize_match_snapshot(paid)})
    assert paid.cards[source.id].zone == destination(mode, seat, source.owner)
    assert len(paid.players[seat].hand) == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mode', ['none', 'rip'])
@pytest.mark.parametrize('suppress', [False, True])
def test_cycle_or_discard_watch_fires_once_for_one_real_cost(request, monkeypatch, seat, mode, suppress):
    state, source, action = cycle_position(seat, 'Lonely Sandbar', mode)
    watcher = add(state, 'Archfiend of Ifnir', seat)
    opposing = add(state, 'Krosan Tusker', 3 - seat)
    if suppress:
        add(state, 'Dress Down', seat)
    paid, events = observed_action(state, seat, source, action, monkeypatch)
    queued = [asdict(item) for item in paid.stack]
    for _ in range(4):
        if not paid.stack:
            break
        assert resolve_top_of_stack(paid)
    actual = paid.cards[opposing.id].counters.get('-1/-1', 0)
    receipt(request, {'action': action, 'events': events, 'queued': queued,
                      'watcher': asdict(watcher), 'expected_counter': 0 if suppress else 1,
                      'actual_counter': actual, 'resolved': serialize_match_snapshot(paid)})
    assert actual == (0 if suppress else 1)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mode', MODES)
def test_real_death_token_is_not_a_card_for_leyline_but_rip_replaces_it(request, monkeypatch, seat, mode):
    state, source, first_action = death_position(seat, 'Reef Worm')
    first, first_events = observed_action(state, seat, source, first_action, monkeypatch)
    assert resolve_top_of_stack(first)
    fish, = tokens(first, seat)
    assert fish.power == fish.toughness == 3 and 'When this token dies' in fish.oracle_text
    host = replacement(first, seat, mode)
    if mode == 'rip':
        emit_event(first, 'enters_battlefield', {'card_id': host.id, 'controller': seat})
        assert resolve_top_of_stack(first)
        assert not first.players[seat].graveyard
    fish.counters['+1/+1'] = 2
    second_tower = add(first, 'Phyrexian Tower', seat)
    second_action = {**first_action, 'card_id': second_tower.id,
                     'payment_choices': {'sacrifice_card_ids': [fish.id]}}
    second, events = observed_action(first, seat, fish, second_action, monkeypatch)
    queued = [asdict(item) for item in second.stack]
    if second.stack:
        assert resolve_top_of_stack(second)
    generated = tokens(second, seat)
    receipt(request, {'first_events': first_events, 'second_action': second_action,
                      'events': events, 'queued': queued, 'original_token': asdict(fish),
                      'expected_new_tokens': 0 if mode == 'rip' else 1,
                      'actual_new_tokens': len(generated),
                      'resolved': serialize_match_snapshot(second)})
    assert second.cards[fish.id].zone == Zone.CEASED
    assert len(generated) == (0 if mode == 'rip' else 1)
    if generated:
        assert generated[0].power == generated[0].toughness == 6
    assert any(row['event'] == 'creature_dies' for row in events) == (mode != 'rip')


@pytest.mark.parametrize('seat', [1, 2])
def test_exact_cycle_or_discard_clause_compiles_effect_independently_of_matcher(request, seat):
    from rules_engine.events import _trigger_from_oracle
    state, source, _ = cycle_position(seat, 'Lonely Sandbar')
    watcher = add(state, 'Archfiend of Ifnir', seat)
    clause = next(line for line in watcher.oracle_text.splitlines()
                  if line.startswith('Whenever you cycle or discard'))
    with cards.unchanged_root(state):
        compiled = _trigger_from_oracle(
            state, watcher.id, seat, clause.lower(), 'canonical clause probe',
            'cycle', {'card_id': source.id, 'controller': seat})
    receipt(request, {'oracle_clause': clause, 'compiled': compiled,
                      'coverage_warnings': known_unsupported_mechanics(watcher.oracle_text),
                      'setup': serialize_match_snapshot(state)})
    assert compiled['effect_key'] not in {'noop', 'discard_cards'}
