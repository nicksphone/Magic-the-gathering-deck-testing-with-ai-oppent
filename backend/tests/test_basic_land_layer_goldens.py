"""Canonical layer goldens for bounded basic-land replacement acceptance."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path
import subprocess
import sys

import pytest

from ai.information import decision_view
from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_card_view, serialize_match_snapshot
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.attachments import attach_if_legal
from rules_engine.continuous import has_keyword, printed_abilities_suppressed
from rules_engine.engine import RulesEngine
from rules_engine.events import capture_last_known_battlefield, emit_event
from rules_engine.land_types import effective_type_line, land_type_instructions
from rules_engine.mana import mana_source_outputs
from rules_engine.query_context import rule_query_scope
from rules_engine.type_effects import effective_types
from tests.test_ai_recurring_engines import fixture, add as raw_add, resolve


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / 'fixtures/basic_land_layer_goldens'
CARDS = {row['name']: row for row in json.loads((FIXTURES / 'cards.json').read_text())}
def position(seat):
    state = fixture()
    state.active_player = state.priority_player = seat
    for player in state.players.values():
        player.mana_pool = dict.fromkeys('WUBRGC', 10)
    return state


def add(state, name, seat, zone=Zone.BATTLEFIELD):
    card = raw_add(state, name, seat, zone, cards=CARDS)
    card.summoning_sick = False
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
    return card


def setter(state, name, seat, target):
    source = add(state, name, seat)
    if name != 'Blood Moon':
        assert attach_if_legal(state, source.id, target.id)
    return source


def public_query(state, cid, seat):
    with rule_query_scope(state):
        return {
            'types': effective_types(state, cid),
            'line': effective_type_line(state, state.cards[cid]),
            'suppressed': printed_abilities_suppressed(state, cid),
            'mana': mana_source_outputs(state, seat, cid),
            'flying': has_keyword(state, cid, 'flying'),
        }


def test_fixture_fields_are_exact_committed_canonical_rows():
    provenance = json.loads((FIXTURES / 'provenance.json').read_text())
    for entry in provenance['cards']:
        content = (ROOT / entry['source']).read_bytes()
        assert hashlib.sha256(content).hexdigest() == entry['source_sha256']
        raw = next(row for row in json.loads(content) if row['name'] == entry['name'])
        assert CARDS[entry['name']] == {key: raw[key] for key in entry['fields']}
        assert raw['oracle_id'] and raw['id']


def test_parser_receipt_is_bounded_not_canonical_card_certification():
    for name in ['Spreading Seas', 'Blood Moon', 'Lush Growth']:
        assert land_type_instructions(CARDS[name]['oracle_text'])
    assert not land_type_instructions(CARDS['Song of the Dryads']['oracle_text'])


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,color', [('Blood Moon', 'R'), ('Spreading Seas', 'U'), ('Lush Growth', 'G')])
def test_subtype_setting_preserves_creature_and_printed_identity_without_query_writes(seat, name, color):
    state = position(seat)
    arbor = add(state, 'Dryad Arbor', seat)
    setter(state, name, 3-seat, arbor)
    before = serialize_match_snapshot(state)
    expected = public_query(state, arbor.id, seat)
    assert expected['types'] == ['Land', 'Creature']
    assert expected['suppressed']
    assert color in expected['mana'] and 'Dryad' in expected['line']
    for candidate in [state, deserialize_match_snapshot(before)]:
        assert public_query(candidate, arbor.id, seat) == expected
        assert candidate.cards[arbor.id].oracle_text == CARDS['Dryad Arbor']['oracle_text']
        assert candidate.cards[arbor.id].colors == CARDS['Dryad Arbor']['colors']
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,color', [('Blood Moon', 'R'), ('Spreading Seas', 'U')])
def test_only_intrinsic_new_mana_is_executable_and_old_color_rejection_is_atomic(seat, name, color):
    state = position(seat)
    land = add(state, 'Hallowed Fountain', seat)
    setter(state, name, 3-seat, land)
    assert mana_source_outputs(state, seat, land.id) == {color: 1}
    views = [m for m in RulesEngine().legal_moves(state, seat)
             if m['type'] == 'activate_mana_ability' and m.get('card_id') == land.id]
    assert len(views) == 1 and views[0]['outputs'] == {color: 1}
    action = {'type': 'activate_mana_ability', 'card_id': land.id,
              'ability_index': views[0]['ability_index'], 'color': 'W'}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before
    count = state.players[seat].mana_pool[color]
    result = checked_action(state, RulesEngine(), seat, {**action, 'color': color})
    assert result.players[seat].mana_pool[color] == count + 1
    assert result.cards[land.id].tapped and not result.stack


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Blood Moon', 'Spreading Seas'])
@pytest.mark.parametrize('grant_first', [False, True])
def test_real_jump_grant_survives_land_subtype_setting_regardless_of_timestamp(seat, name, grant_first):
    state = position(seat)
    arbor = add(state, 'Dryad Arbor', seat)
    if not grant_first:
        setter(state, name, 3-seat, arbor)
    jump = add(state, 'Jump', seat, Zone.HAND)
    state = resolve(checked_action(state, RulesEngine(), seat,
        {'type': 'cast_spell', 'card_id': jump.id, 'targets': {'target_card_id': arbor.id}}))
    if grant_first:
        setter(state, name, 3-seat, state.cards[arbor.id])
    for candidate in [state, deserialize_match_snapshot(serialize_match_snapshot(state))]:
        assert printed_abilities_suppressed(candidate, arbor.id)
        assert has_keyword(candidate, arbor.id, 'flying')
    RulesEngine()._clear_marked_damage(state)
    assert not has_keyword(state, arbor.id, 'flying')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('reverse', [False, True])
def test_same_layer_dependency_overrides_timestamp_but_independent_setters_do_not(seat, reverse):
    state = position(seat)
    names = ['Urborg, Tomb of Yawgmoth', 'Blood Moon']
    for name in reversed(names) if reverse else names:
        add(state, name, seat)
    land = add(state, 'Hallowed Fountain', seat)
    assert mana_source_outputs(state, seat, land.id) == {'R': 1}
    state = position(seat)
    names = ['Blood Moon', 'Prismatic Omen']
    for name in reversed(names) if reverse else names:
        add(state, name, seat)
    land = add(state, 'Hallowed Fountain', seat)
    assert mana_source_outputs(state, seat, land.id) == ({'R': 1} if reverse else dict.fromkeys('WUBRG', 1))


@pytest.mark.parametrize('seat', [1, 2])
def test_reattachment_retimes_aura_and_mutation_is_between_immutable_scopes(seat):
    state = position(seat)
    lands = [add(state, 'Hallowed Fountain', seat) for _ in range(2)]
    seas = setter(state, 'Spreading Seas', 3-seat, lands[0])
    add(state, 'Blood Moon', 3-seat)
    old = seas.effect_timestamp
    assert public_query(state, lands[0].id, seat)['mana'] == {'R': 1}
    assert attach_if_legal(state, seas.id, lands[1].id)
    assert seas.effect_timestamp > old
    assert public_query(state, lands[0].id, seat)['mana'] == {'R': 1}
    assert public_query(state, lands[1].id, seat)['mana'] == {'U': 1}
    resolve_effect(state, seat, 'destroy_permanent', {'target_card_id': seas.id})
    assert public_query(state, lands[1].id, seat)['mana'] == {'R': 1}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Spreading Seas', 'Song of the Dryads'])
def test_canonical_aura_cast_acceptance_is_not_layer_certification(seat, name):
    state = position(seat)
    target = add(state, 'Dryad Arbor', seat)
    spell = add(state, name, seat, Zone.HAND)
    state = resolve(checked_action(state, RulesEngine(), seat,
        {'type': 'cast_spell', 'card_id': spell.id, 'targets': {'target_card_id': target.id}}))
    assert state.cards[spell.id].zone == Zone.BATTLEFIELD
    assert state.cards[spell.id].attached_to == target.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('facet', ['card_types', 'subtypes', 'colors', 'printed_loss', 'intrinsic_mana'])
def test_song_characteristic_facets_are_independent_goldens(seat, facet):
    state = position(seat)
    target = add(state, 'Royal Assassin', seat)
    setter(state, 'Song of the Dryads', 3-seat, target)
    if facet == 'card_types':
        assert effective_types(state, target) == ['Land']
    elif facet == 'subtypes':
        assert effective_type_line(state, target) == 'Land \u2014 Forest'
    elif facet == 'colors':
        assert serialize_card_view(state, target.id)['colors'] == []
    elif facet == 'printed_loss':
        assert printed_abilities_suppressed(state, target.id)
    else:
        assert mana_source_outputs(state, seat, target.id) == {'G': 1}


@pytest.mark.parametrize('seat', [1, 2])
def test_song_generic_activated_ability_must_be_hidden_and_checked_rejected(seat):
    state = position(seat)
    assassin = add(state, 'Royal Assassin', seat)
    victim = add(state, 'Llanowar Elves', 3-seat)
    victim.tapped = True
    assert any(m['type'] == 'activate_ability' and m.get('card_id') == assassin.id
               for m in RulesEngine().legal_moves(state, seat))
    setter(state, 'Song of the Dryads', 3-seat, assassin)
    before = serialize_match_snapshot(state)
    rejected = False
    try:
        checked_action(state, RulesEngine(), seat, {'type': 'activate_ability', 'card_id': assassin.id,
            'ability_index': 0, 'targets': {'target_card_id': victim.id}})
    except ActionRejected:
        rejected = True
    assert rejected, 'A printed ability on the converted land remains executable'
    assert serialize_match_snapshot(state) == before
    assert not any(m['type'] == 'activate_ability' and m.get('card_id') == assassin.id
                   for m in RulesEngine().legal_moves(state, seat))


@pytest.mark.parametrize('seat', [1, 2])
def test_song_removes_printed_keyword_not_earlier_resolved_jump(seat):
    state = position(seat)
    boa = add(state, 'River Boa', seat)
    jump = add(state, 'Jump', seat, Zone.HAND)
    state = resolve(checked_action(state, RulesEngine(), seat,
        {'type': 'cast_spell', 'card_id': jump.id, 'targets': {'target_card_id': boa.id}}))
    setter(state, 'Song of the Dryads', 3-seat, state.cards[boa.id])
    assert has_keyword(state, boa.id, 'flying')
    assert not has_keyword(state, boa.id, 'islandwalk')


@pytest.mark.parametrize('seat', [1, 2])
def test_song_blocks_new_creature_only_grant_without_committing_costs(seat):
    state = position(seat)
    boa = add(state, 'River Boa', seat)
    setter(state, 'Song of the Dryads', 3-seat, boa)
    jump = add(state, 'Jump', seat, Zone.HAND)
    before = serialize_match_snapshot(state)
    rejected = False
    try:
        checked_action(state, RulesEngine(), seat, {'type': 'cast_spell',
            'card_id': jump.id, 'targets': {'target_card_id': boa.id}})
    except ActionRejected:
        rejected = True
    assert rejected, 'A land must not remain a legal creature-only target'
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_song_prevents_new_printed_entry_triggers(seat):
    state = position(seat)
    warden = add(state, 'Soul Warden', seat)
    setter(state, 'Song of the Dryads', 3-seat, warden)
    entrant = add(state, 'Llanowar Elves', seat)
    emit_event(state, 'enters_battlefield', {'card_id': entrant.id, 'controller': seat})
    assert not any(item.source_card_id == warden.id for item in state.stack)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('facet', ['lki', 'departure'])
def test_song_source_lki_records_suppression_before_departure(seat, facet):
    state = position(seat)
    artist = add(state, 'Blood Artist', seat)
    setter(state, 'Song of the Dryads', 3-seat, artist)
    capture_last_known_battlefield(state, artist.id)
    if facet == 'lki':
        assert artist.last_known_battlefield['printed_abilities_suppressed']
        assert artist.last_known_battlefield['types'] == ['Land']
    else:
        resolve_effect(state, 3-seat, 'destroy_permanent', {'target_card_id': artist.id})
        assert not any(item.source_card_id == artist.id for item in state.stack)


@pytest.mark.parametrize('seat', [1, 2])
def test_song_on_static_loss_source_stops_its_printed_continuous_effect(seat):
    state = position(seat)
    elf = add(state, 'Llanowar Elves', seat)
    humility = add(state, 'Humility', 3-seat)
    assert mana_source_outputs(state, seat, elf.id) == {}
    setter(state, 'Song of the Dryads', seat, humility)
    assert mana_source_outputs(state, seat, elf.id) == {'G': 1}


@pytest.mark.parametrize('seat', [1, 2])
def test_song_removes_land_type_setter_source_before_its_same_layer_effect(seat):
    state = position(seat)
    land = add(state, 'Hallowed Fountain', seat)
    moon = add(state, 'Blood Moon', 3-seat)
    assert mana_source_outputs(state, seat, land.id) == {'R': 1}
    setter(state, 'Song of the Dryads', seat, moon)
    assert mana_source_outputs(state, seat, land.id) == {'W': 1, 'U': 1}
    assert mana_source_outputs(state, 3-seat, moon.id) == {'G': 1}


@pytest.mark.parametrize('seat', [1, 2])
def test_already_stacked_printed_trigger_survives_song_and_source_departure(seat):
    state = position(seat)
    warden = add(state, 'Soul Warden', seat)
    entrant = add(state, 'Llanowar Elves', seat)
    emit_event(state, 'enters_battlefield', {'card_id': entrant.id, 'controller': seat})
    assert any(item.source_card_id == warden.id for item in state.stack)
    setter(state, 'Song of the Dryads', 3-seat, warden)
    resolve_effect(state, 3-seat, 'destroy_permanent', {'target_card_id': warden.id})
    life = state.players[seat].life
    state = resolve(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert state.players[seat].life == life + 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Spreading Seas', 'Song of the Dryads'])
def test_decision_projection_is_hidden_info_invariant_pure_and_fresh_process_replayable(seat, name):
    state = position(seat)
    land = add(state, 'Dryad Arbor', seat)
    setter(state, name, 3-seat, land)
    hidden = add(state, 'Royal Assassin', 3-seat, Zone.HAND)
    before = serialize_match_snapshot(state)
    moves = RulesEngine().legal_moves(state, seat)
    view, _ = decision_view(state, seat, moves)
    changed = deserialize_match_snapshot(before)
    prototype = add(position(seat), 'Soul Warden', 3-seat, Zone.HAND)
    # Perturb private identities with complete canonical rows, not hybrid cards.
    for cid in [hidden.id, *changed.players[3-seat].library]:
        replacement = deepcopy(prototype)
        original = changed.cards[cid]
        replacement.id, replacement.zone = cid, original.zone
        replacement.owner, replacement.controller = original.owner, original.controller
        changed.cards[cid] = replacement
    other, _ = decision_view(changed, seat, RulesEngine().legal_moves(changed, seat))
    assert serialize_match_snapshot(view) == serialize_match_snapshot(other)
    assert not view.cards[hidden.id].oracle_text and not view.cards[hidden.id].name
    assert public_query(view, land.id, seat) == public_query(state, land.id, seat)
    assert serialize_match_snapshot(state) == before
    script = '''import json,sys
from game_state.serializers import deserialize_match_snapshot
from rules_engine.land_types import effective_type_line
from rules_engine.mana import mana_source_outputs
s=deserialize_match_snapshot(json.load(sys.stdin))
cid=sys.argv[1];seat=int(sys.argv[2])
print(json.dumps([effective_type_line(s,s.cards[cid]),mana_source_outputs(s,seat,cid)]))
'''
    result = subprocess.run([sys.executable, '-c', script, land.id, str(seat)],
        cwd=ROOT / 'backend', input=json.dumps(before), text=True, capture_output=True,
        check=True, timeout=30)
    assert json.loads(result.stdout) == [effective_type_line(state, land),
                                        mana_source_outputs(state, seat, land.id)]


@pytest.mark.parametrize('seat', [1, 2])
def test_already_stacked_activation_survives_song_and_source_departure(seat):
    state = position(seat)
    assassin = add(state, 'Royal Assassin', seat)
    victim = add(state, 'Llanowar Elves', 3-seat)
    victim.tapped = True
    state = checked_action(state, RulesEngine(), seat, {'type': 'activate_ability',
        'card_id': assassin.id, 'ability_index': 0, 'targets': {'target_card_id': victim.id}})
    assert any(item.source_card_id == assassin.id for item in state.stack)
    setter(state, 'Song of the Dryads', 3-seat, state.cards[assassin.id])
    resolve_effect(state, 3-seat, 'destroy_permanent', {'target_card_id': assassin.id})
    state = resolve(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert state.cards[victim.id].zone == Zone.GRAVEYARD
