"""Strict canonical color-consumer requirements, not whole-card certification."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys

import pytest

from ai.information import decision_view
from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Zone, assign_static_order_on_battlefield_entry, object_incarnation
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.continuous import effective_keywords
from rules_engine.engine import RulesEngine
from rules_engine.query_context import rule_query_scope
from rules_engine.colors import card_color_names
from rules_engine.targeting import validate_protection_targets
from tests.test_basic_land_hooks import attach_song_fixture, cast_song, checked
from tests.test_basic_land_layer_goldens import position
from tests.test_ai_recurring_engines import resolve


ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = json.loads((Path(__file__).parent / 'fixtures/color_consumer_goldens/provenance.json').read_text())
CARDS = {entry['row']['name']: entry['row'] for entry in RECEIPTS}


@pytest.fixture(autouse=True)
def no_database_or_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('State-only goldens must not connect to SQLite or a socket')
    monkeypatch.setattr(sqlite3, 'connect', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket.socket, 'connect_ex', forbidden)


def add(state, name, seat, zone=Zone.BATTLEFIELD):
    sample = MatchFactory.from_decks([{**CARDS[name], 'card_name': name, 'quantity': 1}], [], seed=71)
    card = next(iter(sample.cards.values()))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(zone)
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    card.summoning_sick = False
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
    return card


def restart(state):
    snapshot = serialize_match_snapshot(state)
    resumed = deserialize_match_snapshot(deepcopy(snapshot))
    assert serialize_match_snapshot(state) == snapshot
    assert serialize_match_snapshot(resumed) == snapshot
    return resumed


def retained_damage(seat, converted):
    state = position(seat)
    source = add(state, 'Prodigal Pyromancer', seat)
    target = add(state, 'Etched Champion', 3-seat)
    add(state, 'Bonesplitter', 3-seat)
    assert 'protection from red' not in effective_keywords(state, target.id)
    root = serialize_match_snapshot(state)
    state = checked(state, seat, {'type': 'activate_ability', 'card_id': source.id,
        'ability_index': 0, 'targets': {'target_card_id': target.id}})
    assert root['stack'] == []
    item = state.stack[-1]
    assert item.controller == seat and item.source_card_id == source.id
    # Controlled canonical response-position setup, NOT a played episode:
    # the third artifact turns on Champion's real metalcraft protection;
    # Song attachment does not pretend to be a legal sorcery response.
    add(state, 'Bonesplitter', 3-seat)
    if converted:
        state = attach_song_fixture(state, source.id, seat)
    assert 'protection from red' in effective_keywords(state, target.id)
    assert card_color_names(state.cards[source.id], state) == (set() if converted else {'red'})
    assert state.stack[-1].id == item.id
    return state, source.id, target.id, item.id


def resolve_copy(state):
    before = serialize_match_snapshot(state)
    result = resolve(restart(state))
    assert serialize_match_snapshot(state) == before
    return result


def test_exact_canonical_rows_without_oracle_mutation():
    for entry in RECEIPTS:
        content = (ROOT / entry['source']).read_bytes()
        assert hashlib.sha256(content).hexdigest() == entry['source_sha256']
        assert entry['row'] == next(row for row in json.loads(content) if row['name'] == entry['row']['name'])
        assert entry['row']['oracle_id']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('resumed', [False, True])
def test_live_converted_source_damage_is_not_prevented_as_printed_red(seat, resumed):
    state, source, target, item = retained_damage(seat, True)
    assert '__source_lki' not in state.stack[-1].payload
    if resumed:
        state = restart(state)
    before = serialize_match_snapshot(state)
    with rule_query_scope(state):
        assert validate_protection_targets(state, state.cards[source], {'target_card_id': target})[0]
    assert serialize_match_snapshot(state) == before
    result = resolve_copy(state)
    assert not any(entry.id == item for entry in result.stack)
    assert result.cards[target].zone == Zone.BATTLEFIELD
    assert result.cards[target].counters.get('__damage_marked', 0) == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('converted', [False, True])
@pytest.mark.parametrize('reenter', [False, True])
def test_departed_source_lki_and_incarnation_control_old_stack_resolution(seat, converted, reenter):
    state, source, target, item_id = retained_damage(seat, converted)
    old_handle = object_incarnation(state.cards[source])
    # Canonical effect primitive, not a claim that a land was legally Unsummoned.
    resolve_effect(state, seat, 'return_permanent_to_hand', {'target_card_id': source})
    item = next(entry for entry in state.stack if entry.id == item_id)
    receipt = deepcopy(item.payload['__source_lki'])
    assert receipt['color_names'] == ([] if converted else ['red'])
    assert receipt['battlefield_incarnation'] == old_handle
    assert item.controller == seat
    if reenter:
        # Controlled same-ID new incarnation, explicitly not a creature spell cast.
        card = state.cards[source]
        state.players[seat].hand.remove(source)
        card.move_to_zone(Zone.BATTLEFIELD)
        state.players[seat].battlefield.append(source)
        assign_static_order_on_battlefield_entry(state, source)
        assert object_incarnation(card) != old_handle
        if not converted:
            state = attach_song_fixture(state, source, seat)
        assert card_color_names(state.cards[source], state) == ({'red'} if converted else set())
        assert state.stack[-1].payload['__source_lki'] == receipt
    state = restart(state)
    assert state.stack[-1].payload['__source_lki'] == receipt
    result = resolve_copy(state)
    assert result.cards[target].counters.get('__damage_marked', 0) == int(converted)
    fizzled = any('does not resolve because its target is illegal' in line for line in result.log)
    assert fizzled == (not converted)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('resumed', [False, True])
def test_actual_ugin_selection_keeps_colorless_land_and_exiles_colored_control(seat, resumed):
    state = position(seat)
    converted = add(state, 'Savannah Lions', 3-seat)
    control = add(state, 'Savannah Lions', seat)
    state = cast_song(state, converted.id, seat)
    source = add(state, 'Ugin, the Spirit Dragon', seat)
    assert card_color_names(state.cards[converted.id], state) == set()
    assert card_color_names(state.cards[control.id], state) == {'white'}
    if resumed:
        state = restart(state)
    state = checked(state, seat, {'type': 'activate_loyalty', 'card_id': source.id,
        'ability_index': 1, 'targets': {'x_value': 1}})
    assert state.stack[-1].effect_key == 'exile_colored_permanents_mana_value_at_most'
    result = resolve_copy(state)
    assert result.cards[control.id].zone == Zone.EXILE
    assert result.cards[converted.id].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('resource_owner', ['self', 'opponent'])
@pytest.mark.parametrize('resumed', [False, True])
@pytest.mark.parametrize('resource_name', ['Savannah Lions', 'Royal Assassin'])
def test_actual_song_changes_color_condition_without_printed_identity_leak(seat, resource_owner, resumed, resource_name):
    state = position(seat)
    guard = add(state, 'Abzan Kin-Guard', seat)
    resource = add(state, resource_name, seat if resource_owner == 'self' else 3-seat)
    assert ('lifelink' in effective_keywords(state, guard.id)) == (resource_owner == 'self')
    state = cast_song(state, resource.id, seat)
    assert state.cards[resource.id].colors == CARDS[resource_name]['colors']
    assert card_color_names(state.cards[resource.id], state) == set()
    if resumed:
        state = restart(state)
    before = serialize_match_snapshot(state)
    with rule_query_scope(state):
        result = effective_keywords(state, guard.id)
    assert serialize_match_snapshot(state) == before
    assert 'lifelink' not in result


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_departure_old_black_ability_cannot_use_new_colorless_incarnation(seat):
    state = position(seat)
    source = add(state, 'Royal Assassin', seat)
    target = add(state, 'Knight of Grace', seat)
    target.tapped = True
    # Hexproof only constrains opponents: this real activation is initially legal.
    state = checked(state, seat, {'type': 'activate_ability', 'card_id': source.id,
        'ability_index': 0, 'targets': {'target_card_id': target.id}})
    item_id = state.stack[-1].id
    bounce = add(state, 'Unsummon', seat, Zone.HAND)
    state = checked(state, seat, {'type': 'cast_spell', 'card_id': bounce.id,
        'targets': {'target_card_id': source.id}})
    for _ in range(8):
        if state.cards[bounce.id].zone != Zone.STACK:
            break
        state = checked(state, state.priority_player, {'type': 'pass_priority'})
    assert state.cards[bounce.id].zone == Zone.GRAVEYARD
    assert state.cards[source.id].zone == Zone.HAND
    item = next(entry for entry in state.stack if entry.id == item_id)
    receipt = deepcopy(item.payload['__source_lki'])
    assert receipt['color_names'] == ['black'] and item.controller == seat
    # Controlled reentry, attachment and target-controller transfer, not legal casts.
    card = state.cards[source.id]
    state.players[seat].hand.remove(card.id)
    card.move_to_zone(Zone.BATTLEFIELD)
    state.players[seat].battlefield.append(card.id)
    assign_static_order_on_battlefield_entry(state, card.id)
    state = attach_song_fixture(state, card.id, seat)
    resolve_effect(state, 3-seat, 'change_control', {'target_card_id': target.id})
    assert object_incarnation(state.cards[source.id]) != receipt['battlefield_incarnation']
    assert not card_color_names(state.cards[source.id], state)
    assert state.cards[target.id].controller == 3-seat
    assert state.stack[-1].payload['__source_lki'] == receipt
    before = serialize_match_snapshot(state)
    result = resolve_copy(state)
    assert serialize_match_snapshot(state) == before
    assert result.cards[target.id].zone == Zone.BATTLEFIELD
    assert any('does not resolve because its target is illegal' in line for line in result.log)


@pytest.mark.parametrize('seat', [1, 2])
def test_real_protected_target_rejects_atomically_and_other_target_resolves(seat):
    state = position(seat)
    target = add(state, 'Etched Champion', 3-seat)
    for _ in range(2):
        add(state, 'Bonesplitter', 3-seat)
    spell = add(state, 'Lightning Bolt', seat, Zone.HAND)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id,
            'targets': {'target_card_id': target.id}})
    assert serialize_match_snapshot(state) == before
    alternate = add(state, 'Knight of Grace', 3-seat)
    result = resolve_copy(checked(state, seat, {'type': 'cast_spell', 'card_id': spell.id,
        'targets': {'target_card_id': alternate.id}}))
    assert result.cards[alternate.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_converted_source_has_no_executable_printed_damage_ability(seat):
    state = position(seat)
    source = add(state, 'Prodigal Pyromancer', seat)
    state = cast_song(state, source.id, seat)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'activate_ability', 'card_id': source.id,
            'ability_index': 0, 'targets': {'target_player': 3-seat}})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['damage', 'selector'])
def test_private_counterfactual_and_retained_root_ownership(seat, family):
    if family == 'damage':
        state, source, target, _ = retained_damage(seat, True)
    else:
        state = position(seat)
        source = add(state, 'Abzan Kin-Guard', seat).id
        target = add(state, 'Savannah Lions', seat).id
        state = cast_song(state, target, seat)
    before = serialize_match_snapshot(state)
    changed = restart(state)
    prototype = add(position(seat), 'Soul Warden', 3-seat, Zone.HAND)
    for cid in [*changed.players[3-seat].hand, *changed.players[3-seat].library]:
        card = deepcopy(prototype)
        old = changed.cards[cid]
        card.id, card.owner, card.controller, card.zone = old.id, old.owner, old.controller, old.zone
        changed.cards[cid] = card
    engine = RulesEngine()
    views = []
    outcomes = []
    for candidate in [state, changed]:
        saved = serialize_match_snapshot(candidate)
        view, _ = decision_view(candidate, seat, engine.legal_moves(candidate, seat))
        views.append(serialize_match_snapshot(view))
        with rule_query_scope(candidate):
            outcomes.append((sorted(card_color_names(candidate.cards[source], candidate)),
                             effective_keywords(candidate, target)))
        assert serialize_match_snapshot(candidate) == saved
    assert views[0] == views[1] and outcomes[0] == outcomes[1]
    if family == 'damage':
        a, b = resolve_copy(state), resolve_copy(changed)
        assert a.cards[target].counters == b.cards[target].counters
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_fresh_process_snapshot_color_query_is_pure_without_database(seat):
    state, source, _, _ = retained_damage(seat, True)
    before = serialize_match_snapshot(state)
    script = '''import json,sys,sqlite3,socket
def forbidden(*args,**kwargs): raise AssertionError('No database/network')
sqlite3.connect=forbidden; socket.socket.connect=forbidden; socket.socket.connect_ex=forbidden
from game_state.serializers import deserialize_match_snapshot,serialize_match_snapshot
from rules_engine.colors import card_color_names
s=deserialize_match_snapshot(json.load(sys.stdin)); assert not card_color_names(s.cards[sys.argv[1]],s)
print(json.dumps(serialize_match_snapshot(s),sort_keys=True))
'''
    result = subprocess.run([sys.executable, '-c', script, source], input=json.dumps(before),
        text=True, capture_output=True, cwd=ROOT, check=True)
    assert json.loads(result.stdout) == json.loads(json.dumps(before))
    assert serialize_match_snapshot(state) == before
