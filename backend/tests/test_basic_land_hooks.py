"""Ordinary canonical acceptance for LKI/color and converted-attachment seams."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from ai.information import decision_view
from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Zone, assign_static_order_on_battlefield_entry, object_incarnation
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.attachments import attach_if_legal, attachment_target_is_legal, is_aura, is_equipment
from rules_engine.bestow import is_bestowed
from rules_engine.engine import RulesEngine
from rules_engine.events import capture_last_known_battlefield
from rules_engine.protection import protection_match_reason, source_matches_quality
from rules_engine.query_context import rule_query_scope
from rules_engine.state_based_actions import apply_state_based_actions
from rules_engine.targeting import validate_hexproof_shroud_targets
from rules_engine.type_effects import effective_types
from tests.test_ai_recurring_engines import resolve
from tests.test_basic_land_layer_goldens import CARDS as BASE, position


ROOT = Path(__file__).resolve().parents[2]
RECEIPTS = json.loads((Path(__file__).parent / 'fixtures/basic_land_hooks/provenance.json').read_text())
CARDS = {**BASE, **{entry['row']['name']: entry['row'] for entry in RECEIPTS}}


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


def checked(state, seat, action):
    before = serialize_match_snapshot(state)
    result = checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before
    return result


def cast_song(state, cid, seat):
    song = add(state, 'Song of the Dryads', seat, Zone.HAND)
    state = checked(state, seat, {'type': 'cast_spell', 'card_id': song.id,
                                 'targets': {'target_card_id': cid}})
    # Resolve only this spell, preserving any older activated stack object.
    for _ in range(8):
        if state.cards[song.id].zone != Zone.STACK:
            return state
        state = checked(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Canonical Song did not resolve within eight passes')


def attach_song_fixture(state, cid, seat):
    # A controlled board fixture, not an illegal sorcery-in-response cast.
    song = add(state, 'Song of the Dryads', seat)
    assert attach_if_legal(state, song.id, cid)
    apply_state_based_actions(state)
    return state


def attached(state, name, seat, host):
    zone = Zone.HAND if name in {'Leafcrown Dryad', 'Spreading Seas'} else Zone.BATTLEFIELD
    source = add(state, name, seat, zone)
    if name == 'Leafcrown Dryad':
        state = resolve(checked(state, seat, {'type': 'cast_spell', 'card_id': source.id,
            'cost_choice': {'id': 'bestow'}, 'targets': {'target_card_id': host.id}}))
    elif name == 'Spreading Seas':
        state = resolve(checked(state, seat, {'type': 'cast_spell', 'card_id': source.id,
                                             'targets': {'target_card_id': host.id}}))
    else:
        state = resolve(checked(state, seat, {'type': 'equip', 'card_id': source.id,
                                             'target_card_id': host.id}))
    assert state.cards[source.id].attached_to == host.id
    return state, source.id


def test_exact_canonical_receipts_no_oracle_edits():
    for entry in RECEIPTS:
        content = (ROOT / entry['source']).read_bytes()
        assert hashlib.sha256(content).hexdigest() == entry['source_sha256']
        assert entry['row'] == next(row for row in json.loads(content) if row['name'] == entry['row']['name'])
        assert entry['row']['oracle_id']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field,expected', [('colors', []), ('color_names', []), ('power', None), ('toughness', None)])
def test_actual_song_resolution_records_noncreature_colorless_lki(seat, field, expected):
    state = position(seat)
    source = add(state, 'Royal Assassin', seat)
    state = cast_song(state, source.id, seat)
    capture_last_known_battlefield(state, source.id)
    lki = state.cards[source.id].last_known_battlefield
    assert lki[field] == expected
    assert lki['types'] == ['Land'] and lki['printed_abilities_suppressed']
    assert lki['oracle_text'] == CARDS[source.name]['oracle_text']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('consumer', ['quality', 'protection', 'hexproof'])
def test_live_source_color_uses_current_effective_characteristics(seat, consumer):
    state = position(seat)
    source = add(state, 'Royal Assassin', seat)
    target = add(state, 'Hand of Honor' if consumer == 'protection' else 'Knight of Grace', 3-seat)
    if consumer == 'quality':
        assert source_matches_quality(source, 'black', state=state)
    elif consumer == 'protection':
        assert protection_match_reason(state, target.id, source) == 'black'
    else:
        assert not validate_hexproof_shroud_targets(state, seat, {'target_card_id': target.id}, source)[0]
    state = cast_song(state, source.id, seat)
    source = state.cards[source.id]
    before = serialize_match_snapshot(state)
    with rule_query_scope(state):
        if consumer == 'quality':
            assert not source_matches_quality(source, 'black', state=state)
            assert source_matches_quality(source, 'colorless', state=state)
        elif consumer == 'protection':
            assert protection_match_reason(state, target.id, source) is None
        else:
            assert validate_hexproof_shroud_targets(state, seat, {'target_card_id': target.id}, source)[0]
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Spreading Seas', 'Belt of Giant Strength', 'Leafcrown Dryad'])
def test_actual_converted_attachment_detaches_without_destroying_land(seat, name):
    state = position(seat)
    host = add(state, 'Dryad Arbor', seat)
    state, cid = attached(state, name, seat, host)
    old_handle = object_incarnation(state.cards[cid])
    state = cast_song(state, cid, seat)
    card = state.cards[cid]
    assert card.attached_to is None
    assert card.zone == Zone.BATTLEFIELD and cid in state.players[seat].battlefield
    assert effective_types(state, card) == ['Land']
    assert not is_bestowed(card)
    assert object_incarnation(card) == old_handle
    assert not is_aura(card, state) and not is_equipment(card, state)
    assert card.oracle_text == CARDS[name]['oracle_text']
    resumed = deserialize_match_snapshot(serialize_match_snapshot(state))
    apply_state_based_actions(resumed)
    assert serialize_match_snapshot(resumed) == serialize_match_snapshot(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Spreading Seas', 'Belt of Giant Strength'])
def test_converted_permanent_cannot_reattach_and_rejection_does_not_mutate(seat, name):
    state = position(seat)
    host = add(state, 'Dryad Arbor', seat)
    state, cid = attached(state, name, seat, host)
    state = cast_song(state, cid, seat)
    before = serialize_match_snapshot(state)
    assert not attachment_target_is_legal(state, state.cards[cid], host.id)
    assert not attach_if_legal(state, cid, host.id)
    if name == 'Belt of Giant Strength':
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), seat,
                           {'type': 'equip', 'card_id': cid, 'target_card_id': host.id})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Royal Assassin', 'Prodigal Pyromancer'])
def test_existing_stack_ability_retains_true_departure_lki_and_resolves_after_restart(seat, name):
    state = position(seat)
    source = add(state, name, seat)
    victim = add(state, 'Llanowar Elves', 3-seat)
    victim.tapped = True
    target = {'target_card_id': victim.id} if name == 'Royal Assassin' else {'target_player': 3-seat}
    state = checked(state, seat, {'type': 'activate_ability', 'card_id': source.id,
                                 'ability_index': 0, 'targets': target})
    stack_id = state.stack[-1].id
    state = attach_song_fixture(state, source.id, seat)
    assert state.stack[-1].id == stack_id
    resolve_effect(state, seat, 'destroy_permanent', {'target_card_id': source.id})
    item = next(item for item in state.stack if item.id == stack_id)
    lki = item.payload['__source_lki']
    assert lki['colors'] == [] and lki['color_names'] == []
    assert lki['power'] is None and lki['toughness'] is None
    assert lki['types'] == ['Land']
    before = serialize_match_snapshot(state)
    resumed = deserialize_match_snapshot(before)
    assert next(item for item in resumed.stack if item.id == stack_id).payload['__source_lki'] == lki
    life = resumed.players[3-seat].life
    resumed = resolve(resumed)
    if name == 'Royal Assassin':
        assert resumed.cards[victim.id].zone == Zone.GRAVEYARD
    else:
        assert resumed.players[3-seat].life == life - 1
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Spreading Seas', 'Bonesplitter', 'Leafcrown Dryad'])
def test_normal_illegal_host_departure_preserves_aura_equipment_bestow_distinction(seat, name):
    state = position(seat)
    host = add(state, 'Dryad Arbor', seat)
    state, cid = attached(state, name, seat, host)
    resolve_effect(state, seat, 'destroy_permanent', {'target_card_id': host.id})
    apply_state_based_actions(state)
    card = state.cards[cid]
    if name == 'Spreading Seas':
        assert card.zone == Zone.GRAVEYARD
    else:
        assert card.zone == Zone.BATTLEFIELD and card.attached_to is None
        assert not is_bestowed(card)
        assert ('Creature' in effective_types(state, card)) == (name == 'Leafcrown Dryad')


@pytest.mark.parametrize('seat', [1, 2])
def test_private_counterfactual_queries_and_fresh_process_snapshot_are_pure(seat):
    state = position(seat)
    source = add(state, 'Royal Assassin', seat)
    hidden = add(state, 'Royal Assassin', 3-seat, Zone.HAND)
    state = cast_song(state, source.id, seat)
    before = serialize_match_snapshot(state)
    view, _ = decision_view(state, seat, RulesEngine().legal_moves(state, seat))
    changed = deserialize_match_snapshot(before)
    prototype = add(position(seat), 'Soul Warden', 3-seat, Zone.HAND)
    for cid in [hidden.id, *changed.players[3-seat].library]:
        card = deepcopy(prototype)
        old = changed.cards[cid]
        card.id, card.owner, card.controller, card.zone = old.id, old.owner, old.controller, old.zone
        changed.cards[cid] = card
    other, _ = decision_view(changed, seat, RulesEngine().legal_moves(changed, seat))
    assert serialize_match_snapshot(view) == serialize_match_snapshot(other)
    with rule_query_scope(state):
        assert source_matches_quality(state.cards[source.id], 'colorless', state=state)
    assert serialize_match_snapshot(state) == before
    script = '''import json,sys
from game_state.serializers import deserialize_match_snapshot,serialize_match_snapshot
from rules_engine.protection import source_matches_quality
s=deserialize_match_snapshot(json.load(sys.stdin)); cid=sys.argv[1]
assert source_matches_quality(s.cards[cid],'colorless',state=s)
print(json.dumps(serialize_match_snapshot(s),sort_keys=True))
'''
    result = subprocess.run([sys.executable, '-c', script, source.id], input=json.dumps(before),
                            text=True, capture_output=True, cwd=ROOT / 'backend', check=True)
    assert json.loads(result.stdout) == json.loads(json.dumps(before))


@pytest.mark.parametrize('seat', [1, 2])
def test_source_reentry_cannot_overwrite_old_stack_lki_handle(seat):
    state = position(seat)
    source = add(state, 'Royal Assassin', seat)
    victim = add(state, 'Llanowar Elves', 3-seat)
    victim.tapped = True
    state = checked(state, seat, {'type': 'activate_ability', 'card_id': source.id,
        'ability_index': 0, 'targets': {'target_card_id': victim.id}})
    state = attach_song_fixture(state, source.id, seat)
    resolve_effect(state, seat, 'return_permanent_to_hand', {'target_card_id': source.id})
    old_lki = deepcopy(state.stack[-1].payload['__source_lki'])
    assert old_lki['colors'] == [] and old_lki['types'] == ['Land']
    apply_state_based_actions(state)
    card = state.cards[source.id]
    state.players[seat].hand.remove(card.id)
    card.move_to_zone(Zone.BATTLEFIELD)
    state.players[seat].battlefield.append(card.id)
    assign_static_order_on_battlefield_entry(state, card.id)
    assert object_incarnation(card) != old_lki['battlefield_incarnation']
    capture_last_known_battlefield(state, card.id)
    assert card.last_known_battlefield['colors'] == ['B']
    assert state.stack[-1].payload['__source_lki'] == old_lki
    resumed = resolve(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert resumed.cards[victim.id].zone == Zone.GRAVEYARD
