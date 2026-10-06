"""Canonical activated-cost departures agree with the normal zone transition."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import Zone, allocate_effect_timestamp, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.mana_abilities import mana_ability_specs
from rules_engine.stack_engine import resolve_top_of_stack
from tests import test_spell_cost_overlap_investigation as cards


DIRECTORY = Path(__file__).parent / 'fixtures/activated_sacrifice_identity'
RAW = json.loads((DIRECTORY / 'canonical.json').read_text())
cards.ROWS.update(RAW)


def add(state, name, seat, zone=Zone.BATTLEFIELD):
    card = cards.add(state, name, seat, zone)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
    return card


def activate(state, seat, source, victim=None, color='B'):
    spec = next(spec for spec in mana_ability_specs(source, state) if 'Sacrifice' in spec[1])
    action = {'type': 'activate_mana_ability', 'card_id': source.id,
              'ability_index': spec[0], 'color': color}
    if victim is not None:
        action['payment_choices'] = {'sacrifice_card_ids': [victim.id]}
    with cards.unchanged_root(state):
        return checked_action(state, RulesEngine(), seat, action)


def reference(card):
    return {key: deepcopy(getattr(card, key)) for key in (
        'zone', 'zone_change_sequence', 'battlefield_incarnation', 'suspend_haste',
        'foretell_record', 'was_foretold', 'was_kicked', 'granted_flashback', 'exile_face_down')}


def expected_transition(card, destination):
    expected = deepcopy(card)
    expected.move_to_zone(destination)
    return reference(expected)


def test_canonical_fixture_pins():
    provenance = json.loads((DIRECTORY / 'provenance.json').read_text())
    assert provenance['http_requests'] == 0 and not provenance['facts_modified']
    assert hashlib.sha256((DIRECTORY / 'canonical.json').read_bytes()).hexdigest() == provenance['canonical_json_sha256']
    for name, pin in provenance['rows'].items():
        assert RAW[name]['id'] == pin['id'] and RAW[name]['oracle_id'] == pin['oracle_id']
        encoded = json.dumps(RAW[name], sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        assert hashlib.sha256(encoded).hexdigest() == pin['raw_canonical_sha256']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Phyrexian Tower', 'Basal Thrull'])
@pytest.mark.parametrize('destination', [Zone.GRAVEYARD, Zone.EXILE])
def test_other_and_self_sacrifice_use_normal_identity_transition(seat, name, destination):
    state = cards.position(seat)
    source = add(state, name, seat)
    victim = add(state, 'Raging Goblin', seat) if name == 'Phyrexian Tower' else source
    if destination == Zone.EXILE:
        add(state, 'Rest in Peace', seat)
    expected = expected_transition(victim, destination)
    before_incarnation = victim.battlefield_incarnation
    result = activate(state, seat, source, victim if victim is not source else None)
    departed = result.cards[victim.id]
    assert reference(departed) == expected
    assert victim.id in getattr(result.players[seat], destination.value)
    assert result.players[seat].mana_pool['B'] == 2
    assert departed.last_known_battlefield['battlefield_incarnation'] == before_incarnation


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('destination', [Zone.GRAVEYARD, Zone.EXILE])
def test_death_counters_deferred_but_exile_clears_runtime_with_lki_intact(seat, destination, monkeypatch):
    import rules_engine.events as events
    state = cards.position(seat)
    tower = add(state, 'Phyrexian Tower', seat)
    victim = add(state, 'Hangarback Walker', seat)
    victim.counters['+1/+1'] = 2
    if destination == Zone.EXILE:
        add(state, 'Rest in Peace', seat)
    seen = []
    original = events.emit_event_batch

    def observe(current, event, payloads):
        if (event in {'sacrifice', 'permanent_dies', 'creature_dies'}
                and any(payload.get('card_id') == victim.id for payload in payloads)):
            departed = current.cards[victim.id]
            seen.append((event, departed.zone, dict(departed.counters),
                         deepcopy(departed.last_known_battlefield)))
        return original(current, event, payloads)

    monkeypatch.setattr(events, 'emit_event_batch', observe)
    result = activate(state, seat, tower, victim)
    assert all(lki['counters']['+1/+1'] == 2 and lki['power'] == 2 for _, _, _, lki in seen)
    if destination == Zone.GRAVEYARD:
        assert next(counters for event, _, counters, _ in seen if event == 'creature_dies')['+1/+1'] == 2
        assert result.cards[victim.id].counters == {}
        assert len(result.stack) == 1 and result.stack[0].source_card_id == victim.id
    else:
        assert [event for event, _, _, _ in seen] == ['sacrifice']
        assert seen[0][2] == {} and not result.stack


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('destination', [Zone.GRAVEYARD, Zone.EXILE])
def test_self_sacrifice_draw_trigger_and_source_lki_survive(seat, destination):
    state = cards.position(seat)
    source = add(state, 'Chromatic Star', seat)
    draw = add(state, 'Island', seat, Zone.LIBRARY)
    source.counters['+1/+1'] = 2
    state.players[seat].mana_pool['C'] = 1
    if destination == Zone.EXILE:
        add(state, 'Rest in Peace', seat)
    expected = expected_transition(source, destination)
    result = activate(state, seat, source, color='U')
    assert reference(result.cards[source.id]) == expected
    assert result.players[seat].mana_pool['U'] == 1
    assert result.cards[source.id].last_known_battlefield['counters']['+1/+1'] == 2
    if destination == Zone.GRAVEYARD:
        assert len(result.stack) == 1 and result.stack[0].source_card_id == source.id
        resolve_top_of_stack(result)
        assert draw.id in result.players[seat].hand
    else:
        assert not result.stack and draw.id in result.players[seat].library


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign_owner', [False, True])
@pytest.mark.parametrize('name', ['Phyrexian Tower', 'Basal Thrull'])
def test_owner_destination_is_separate_from_activating_controller(seat, foreign_owner, name):
    state = cards.position(seat)
    source = add(state, name, seat)
    victim = add(state, 'Raging Goblin', seat) if name == 'Phyrexian Tower' else source
    if foreign_owner:
        victim.owner = 3-seat
    expected = expected_transition(victim, Zone.GRAVEYARD)
    result = activate(state, seat, source, victim if victim is not source else None)
    assert reference(result.cards[victim.id]) == expected
    assert victim.id in result.players[victim.owner].graveyard
    assert victim.id not in result.players[seat].battlefield
    assert result.cards[victim.id].last_known_battlefield['controller'] == seat
    assert result.players[seat].mana_pool['B'] == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_suspend_granted_haste_clears_on_actual_departure(seat):
    state = cards.position(seat)
    tower = add(state, 'Phyrexian Tower', seat)
    victim = add(state, 'Riftwing Cloudskate', seat)
    # Legal post-suspend-cast metadata; no printed characteristics are rewritten.
    victim.suspend_haste = {'controller': seat, 'timestamp': allocate_effect_timestamp(state)}
    expected = expected_transition(victim, Zone.GRAVEYARD)
    result = activate(state, seat, tower, victim)
    assert reference(result.cards[victim.id]) == expected
    assert not result.cards[victim.id].suspend_haste


@pytest.mark.parametrize('seat', [1, 2])
def test_actually_foretold_creature_loses_foretold_history_on_departure(seat):
    state = cards.position(seat)
    tower = add(state, 'Phyrexian Tower', seat)
    add(state, 'Dream Devourer', seat)
    victim = add(state, 'Basal Thrull', seat, Zone.HAND)
    state.players[seat].mana_pool['C'] = 2
    state = checked_action(state, RulesEngine(), seat, {'type': 'foretell', 'card_id': victim.id})
    assert state.cards[victim.id].foretell_record
    resolve_top_of_stack(state)
    state.turn += 1
    state.players[seat].mana_pool['B'] = 2
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': victim.id,
        'from_exile': True, 'cost_choice': {'id': 'foretell_0'}})
    resolve_top_of_stack(state)
    victim = state.cards[victim.id]
    assert victim.zone == Zone.BATTLEFIELD and victim.was_foretold
    assert not victim.foretell_record
    expected = expected_transition(victim, Zone.GRAVEYARD)
    result = activate(state, seat, state.cards[tower.id], victim)
    assert reference(result.cards[victim.id]) == expected
    assert not result.cards[victim.id].was_foretold


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('destination', [Zone.GRAVEYARD, Zone.EXILE])
def test_real_engine_created_goat_token_departure_and_cessation(seat, destination):
    state = cards.position(seat)
    tower = add(state, 'Phyrexian Tower', seat)
    maker = add(state, 'Woe Strider', seat, Zone.HAND)
    state.players[seat].mana_pool.update(C=2, B=1)
    state = checked_action(state, RulesEngine(), seat, cards.cast(maker))
    resolve_top_of_stack(state)
    resolve_top_of_stack(state)
    victim, = [state.cards[cid] for cid in state.players[seat].battlefield if state.cards[cid].is_token]
    assert victim.type_line == 'Token Creature - Goat' or 'Goat' in victim.type_line
    if destination == Zone.EXILE:
        add(state, 'Rest in Peace', seat)
    expected = expected_transition(victim, destination)
    result = activate(state, seat, state.cards[tower.id], victim)
    departed = result.cards[victim.id]
    assert departed.zone == Zone.CEASED
    assert departed.zone_change_sequence == expected['zone_change_sequence']
    assert all(victim.id not in getattr(player, zone) for player in result.players.values()
               for zone in ('battlefield', 'graveyard', 'exile'))
    assert result.players[seat].mana_pool['B'] == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_returned_permanent_gets_new_battlefield_incarnation(seat):
    state = cards.position(seat)
    tower = add(state, 'Phyrexian Tower', seat)
    victim = add(state, 'Raging Goblin', seat)
    first = activate(state, seat, tower, victim)
    old_incarnation = first.cards[victim.id].battlefield_incarnation
    returned = deepcopy(first)
    card = returned.cards[victim.id]
    returned.players[seat].graveyard.remove(card.id)
    card.move_to_zone(Zone.BATTLEFIELD)
    returned.players[seat].battlefield.append(card.id)
    assign_static_order_on_battlefield_entry(returned, card.id)
    assert card.battlefield_incarnation != old_incarnation
    returned.cards[tower.id].tapped = False
    expected = expected_transition(card, Zone.GRAVEYARD)
    second = activate(returned, seat, returned.cards[tower.id], card)
    assert reference(second.cards[card.id]) == expected
    assert second.cards[card.id].last_known_battlefield['battlefield_incarnation'] == card.battlefield_incarnation


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('destination', [Zone.GRAVEYARD, Zone.EXILE])
def test_canonical_counter_persistence_exception_is_preserved(seat, destination):
    state = cards.position(seat)
    tower = add(state, 'Phyrexian Tower', seat)
    victim = add(state, 'Skullbriar, the Walking Grave', seat)
    victim.counters['+1/+1'] = 2
    if destination == Zone.EXILE:
        add(state, 'Rest in Peace', seat)
    expected = expected_transition(victim, destination)
    result = activate(state, seat, tower, victim)
    assert reference(result.cards[victim.id]) == expected
    assert result.cards[victim.id].counters == victim.counters
    assert result.cards[victim.id].last_known_battlefield['counters'] == victim.counters
