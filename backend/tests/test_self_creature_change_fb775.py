"""Full-RAW constructed games; genuine payments/frames, plus labeled protocols."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from card_data.sync import ScryfallSyncService
from game_state.copying import copy_match_state
from game_state.state import MatchFactory, Step, Zone, object_incarnation
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.ability_model import build_ability_spec
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.continuous import effective_combat_stats, effective_keywords
from rules_engine.engine import RulesEngine
from rules_engine.land_types import effective_type_line
from rules_engine.library_permissions import creature_types
from rules_engine.oracle_effects import extract_activated_abilities
from rules_engine.type_effects import add_type_effect, effective_types

F = Path(__file__).parent / 'fixtures'
SOURCE = F / 'self_creature_change_fb775/SOURCES.json'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == '1e0cab548079b8791dd354b44518f71c87a8fc9ca3d994adab7cb3d915f57221'
SOURCES = json.loads(SOURCE.read_bytes())


def raw(name):
    entry = SOURCES[name]
    body = (F / entry['file']).read_bytes()
    assert hashlib.sha256(body).hexdigest() == entry['sha256']
    card = json.loads(body)
    assert card['object'] == 'card' and card['name'] == name
    assert card['id'] == entry['id'] and card['oracle_id'] == entry['oracle_id']
    assert len(card) == entry['fields'] >= 60
    return card


def snapshot(state):
    return serialize_match_snapshot(state)


def act(state, seat, action):
    before = snapshot(state)
    result = checked_action(state, RulesEngine(), seat, action)
    assert snapshot(state) == before
    return result


def top(state):
    frame = state.stack[-1].id
    for _ in range(4):
        if not any(item.id == frame for item in state.stack):
            return state
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('The genuine top frame did not finish within four passes')


def drain(state):
    for _ in range(12):
        if not state.stack or state.pending_mechanic_choice:
            return state
        state = top(state)
    raise AssertionError('The genuine stack did not drain within twelve frames')


def priority(state, seat):
    if state.priority_player != seat:
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert state.priority_player == seat
    return state


def cast(state, ids, seat, name, targets=None):
    state = priority(state, seat)
    cid = ids[seat][name]
    assert state.cards[cid].zone == Zone.HAND
    before_pool = dict(state.players[seat].mana_pool)
    result = act(state, seat, {'type': 'cast_spell', 'card_id': cid, 'targets': targets or {}})
    assert result.cards[cid].zone == Zone.STACK
    assert any(item.source_card_id == cid and item.controller == seat for item in result.stack)
    assert sum(result.players[seat].mana_pool.values()) < sum(before_pool.values())
    return result


def position(seat):
    rows = []
    for name in SOURCES:
        obj = raw(name)
        normalized = ScryfallSyncService._normalize_payload(obj, ScryfallSyncService._extract_remote_image_uri(obj))
        rows.append({**obj, **normalized, 'card_name': name,
                     'quantity': 60 - len(SOURCES) + 1 if name == 'Forest' else 1,
                     'card_faces': json.loads(normalized['card_faces_json']), 'colors': obj['colors']})
    state = MatchFactory.from_decks(deepcopy(rows), deepcopy(rows), seed=8437)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.turn = 5
    state.priority_stops = {pid: set(Step) for pid in (1, 2)}
    ids = {1: {}, 2: {}}
    for pid, player in state.players.items():
        for name in SOURCES:
            if name == 'Forest':
                continue
            cid = next(cid for cid in player.hand + player.library if state.cards[cid].name == name)
            ids[pid][name] = cid
            if cid in player.library:
                player.library.remove(cid)
                player.hand.append(cid)
                state.cards[cid].move_to_zone(Zone.HAND)
        player.mana_pool = {'W': 30, 'U': 20, 'G': 20, 'R': 10, 'C': 30}
    state = drain(cast(state, ids, seat, 'Figure of Destiny'))
    cid = ids[seat]['Figure of Destiny']
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    assert effective_combat_stats(state, cid) == (1, 1)
    assert effective_keywords(state, cid) == []
    assert_physical(state.cards[cid])
    return state, ids, cid


def assert_physical(card, name='Figure of Destiny'):
    obj = raw(name)
    record = card.characteristic_record
    expected = {key: obj.get(key, '') for key in ('name', 'mana_cost', 'type_line', 'oracle_text')}
    expected.update(power=int(obj['power']), toughness=int(obj['toughness']),
                    printed_power=obj['power'], printed_toughness=obj['toughness'],
                    keywords=[], types=['Creature'], colors=obj['colors'], loyalty=None,
                    card_faces=[], layout='normal', selected_face_index=None,
                    image_uri=obj['image_uris']['normal'])
    assert record['physical'] == expected
    assert record['version'] == 1


def activate(state, seat, cid, index):
    state = priority(state, seat)
    ability = next(a for a in extract_activated_abilities(state.cards[cid]) if a['index'] == index)
    count = (1, 3, 6)[index]
    assert ability['mana_cost'] == '{R/W}' * count
    before = state.players[seat].mana_pool['W']
    result = act(state, seat, {'type': 'activate_ability', 'card_id': cid,
                 'ability_index': index, 'hybrid_choices': ['W'] * count})
    assert result.players[seat].mana_pool['W'] == before - count
    frame = result.stack[-1]
    assert frame.source_card_id == cid and frame.controller == seat
    assert frame.payload['__ability_raw_effect_text'] == ability['raw_effect_text']
    assert frame.payload['__activation_source_reference'] == {
        'incarnation': object_incarnation(result.cards[cid]),
        'zone_change_sequence': result.cards[cid].zone_change_sequence}
    return result


def upgrade(state, seat, cid, index):
    return drain(activate(state, seat, cid, index))


def all_three(state, seat, cid):
    for index, pt, kinds in ((0, 2, {'kithkin', 'spirit'}),
                             (1, 4, {'kithkin', 'spirit', 'warrior'}),
                             (2, 8, {'kithkin', 'spirit', 'warrior', 'avatar'})):
        state = upgrade(state, seat, cid, index)
        assert effective_combat_stats(state, cid) == (pt, pt)
        assert creature_types(state.cards[cid], state) == kinds
        assert set(effective_keywords(state, cid)) == ({'flying', 'first strike'} if index == 2 else set())
        assert_physical(state.cards[cid])
    return state


def cleanup(state):
    turn = state.turn
    for _ in range(64):
        if state.turn != turn:
            return state
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Native turn cleanup bound reached')


@pytest.mark.parametrize('seat', [1, 2])
def test_extracted_first_complete_raw_instruction_compiles_without_fallback(seat):
    state, ids, cid = position(seat)
    ability = extract_activated_abilities(state.cards[cid])[0]
    proxy = replace(state.cards[cid], oracle_text=ability['raw_effect_text'], mana_cost='')
    before = snapshot(state)
    spec = build_ability_spec(state, proxy, seat, report_unsupported=False)
    assert snapshot(state) == before
    assert spec.effect.key != 'noop'
    assert not spec.used_fallback


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_full_raw_three_upgrades_and_permanent_one_timestamp_overlays(seat):
    state, ids, cid = position(seat)
    record = deepcopy(state.cards[cid].characteristic_record)
    state = all_three(state, seat, cid)
    card = state.cards[cid]
    assert len(card.base_stat_effects) == len(card.type_effects) == 3
    assert all(effect['types'] == [] for effect in card.type_effects)
    assert all(not e['until_end_of_turn'] for e in card.type_effects + card.base_stat_effects + card.keyword_effects)
    assert card.type_effects[-1]['timestamp'] == card.base_stat_effects[-1]['timestamp']
    assert {e['timestamp'] for e in card.keyword_effects} == {card.base_stat_effects[-1]['timestamp']}
    assert card.characteristic_record == record
    state = cleanup(state)
    assert effective_combat_stats(state, cid) == (8, 8)
    assert set(effective_keywords(state, cid)) == {'flying', 'first strike'}


@pytest.mark.parametrize('seat', [1, 2])
def test_eight_eight_then_paid_first_ability_keeps_both_granted_keywords(seat):
    state, ids, cid = position(seat)
    state = upgrade(all_three(state, seat, cid), seat, cid, 0)
    assert effective_combat_stats(state, cid) == (2, 2)
    assert creature_types(state.cards[cid], state) == {'kithkin', 'spirit'}
    assert set(effective_keywords(state, cid)) == {'flying', 'first strike'}
    assert_physical(state.cards[cid])


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('index', [1, 2])
def test_conditional_upgrade_can_be_paid_without_required_subtype_but_resolves_without_effect(seat, index):
    state, ids, cid = position(seat)
    before = deepcopy(state.cards[cid])
    state = drain(activate(state, seat, cid, index))
    assert effective_combat_stats(state, cid) == (1, 1)
    assert creature_types(state.cards[cid], state) == {'kithkin'}
    assert state.cards[cid].characteristic_record == before.characteristic_record
    assert not state.cards[cid].type_effects and not state.cards[cid].base_stat_effects and not state.cards[cid].keyword_effects


@pytest.mark.parametrize('seat', [1, 2])
def test_resolution_subtype_can_become_true_via_genuine_response_activation(seat):
    state, ids, cid = position(seat)
    state = activate(state, seat, cid, 1)
    old = state.stack[-1].id
    state = activate(state, seat, cid, 0)
    state = top(state)
    assert [item.id for item in state.stack] == [old]
    assert effective_combat_stats(state, cid) == (2, 2)
    state = drain(state)
    assert effective_combat_stats(state, cid) == (4, 4)


@pytest.mark.parametrize('seat', [1, 2])
def test_resolution_subtype_lost_to_paid_frog_response_prevents_upgrade(seat):
    state, ids, cid = position(seat)
    state = activate(upgrade(state, seat, cid, 0), seat, cid, 1)
    state = top(cast(state, ids, seat, 'Turn to Frog', {'target_card_id': cid}))
    assert creature_types(state.cards[cid], state) == {'frog'}
    assert effective_combat_stats(state, cid) == (1, 1)
    state = drain(state)
    assert effective_combat_stats(state, cid) == (1, 1)
    state = cleanup(state)
    assert effective_combat_stats(state, cid) == (2, 2)
    assert creature_types(state.cards[cid], state) == {'kithkin', 'spirit'}


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_blink_response_invalidates_old_upgrade_without_touching_returning_object(seat):
    state, ids, cid = position(seat)
    state = activate(upgrade(upgrade(state, seat, cid, 0), seat, cid, 1), seat, cid, 2)
    old_ref = deepcopy(state.stack[-1].payload['__activation_source_reference'])
    state = top(cast(state, ids, seat, 'Cloudshift', {'target_card_id': cid}))
    card = state.cards[cid]
    assert card.zone == Zone.BATTLEFIELD
    assert (object_incarnation(card), card.zone_change_sequence) != (old_ref['incarnation'], old_ref['zone_change_sequence'])
    state = drain(deserialize_match_snapshot(snapshot(state)))
    assert effective_combat_stats(state, cid) == (1, 1)
    assert creature_types(state.cards[cid], state) == {'kithkin'}
    assert not state.cards[cid].type_effects and not state.cards[cid].base_stat_effects
    assert not state.cards[cid].keyword_effects
    assert_physical(state.cards[cid])


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_bounce_then_paid_recast_restores_physical_baseline(seat):
    state, ids, cid = position(seat)
    state = all_three(state, seat, cid)
    old_ref = object_incarnation(state.cards[cid]), state.cards[cid].zone_change_sequence
    state = drain(cast(state, ids, seat, 'Unsummon', {'target_card_id': cid}))
    assert state.cards[cid].zone == Zone.HAND
    assert state.cards[cid].keywords == [] and state.cards[cid].power == state.cards[cid].toughness == 1
    state = drain(cast(state, ids, seat, 'Figure of Destiny'))
    assert (object_incarnation(state.cards[cid]), state.cards[cid].zone_change_sequence) != old_ref
    assert effective_combat_stats(state, cid) == (1, 1)
    assert effective_keywords(state, cid) == []
    assert_physical(state.cards[cid])


@pytest.mark.parametrize('seat', [1, 2])
def test_pending_snapshot_and_native_state_copy_replay_without_aliasing(seat):
    state, ids, cid = position(seat)
    state = activate(state, seat, cid, 0)
    before = snapshot(state)
    outcomes = []
    for candidate in (copy_match_state(state), deserialize_match_snapshot(before)):
        assert snapshot(candidate) == before
        resolved = drain(candidate)
        assert effective_combat_stats(resolved, cid) == (2, 2)
        outcomes.append(snapshot(resolved))
        resolved.cards[cid].type_effects[-1]['creature_subtypes'].append('elf')
        assert snapshot(state) == before
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize('seat', [1, 2])
def test_genuine_lithoform_copy_keeps_same_source_and_independent_native_stack_id(seat):
    state, ids, cid = position(seat)
    state = drain(cast(state, ids, seat, 'Lithoform Engine'))
    state = activate(state, seat, cid, 0)
    original = deepcopy(state.stack[-1])
    before_pool = sum(state.players[seat].mana_pool.values())
    state = act(state, seat, {'type': 'activate_ability', 'card_id': ids[seat]['Lithoform Engine'],
                'ability_index': 0, 'targets': {'target_stack_id': original.id}})
    assert sum(state.players[seat].mana_pool.values()) == before_pool - 2
    assert state.cards[ids[seat]['Lithoform Engine']].tapped
    state = top(state)
    assert len(state.stack) == 2 and len({item.id for item in state.stack}) == 2
    assert all(item.source_card_id == cid for item in state.stack)
    copied = next(item for item in state.stack if item.id != original.id)
    assert copied.payload['__stack_copy_kind'] == 'activated'
    assert copied.payload['__activation_source_reference'] == original.payload['__activation_source_reference']
    state = drain(deserialize_match_snapshot(snapshot(state)))
    assert effective_combat_stats(state, cid) == (2, 2)
    assert len(state.cards[cid].base_stat_effects) == len(state.cards[cid].type_effects) == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_clone_does_not_copy_non_copiable_upgrades_and_binds_its_own_upgrade(seat):
    state, ids, cid = position(seat)
    state = all_three(state, seat, cid)
    state = drain(cast(state, ids, seat, 'Clone'))
    pending = state.pending_mechanic_choice
    assert pending and pending['kind'] == 'entry_copy' and pending['player_id'] == seat
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': [cid]})
    state = drain(state)
    clone = ids[seat]['Clone']
    assert state.cards[clone].zone == Zone.BATTLEFIELD
    assert effective_combat_stats(state, clone) == (1, 1)
    assert effective_keywords(state, clone) == []
    assert_physical(state.cards[clone], 'Clone')
    assert state.cards[clone].characteristic_record['values']['name'] == 'Figure of Destiny'
    state = upgrade(state, seat, clone, 0)
    assert effective_combat_stats(state, clone) == (2, 2)
    assert effective_combat_stats(state, cid) == (8, 8)
    assert effective_keywords(state, clone) == []
    assert set(effective_keywords(state, cid)) == {'flying', 'first strike'}
    assert state.cards[clone].type_effects[-1]['source_card_id'] == clone


@pytest.mark.parametrize('seat', [1, 2])
def test_real_counter_and_temporary_modifier_survive_base_set_and_cleanup(seat):
    state, ids, cid = position(seat)
    state = drain(cast(state, ids, seat, 'Battlegrowth', {'target_card_id': cid}))
    state = drain(cast(state, ids, seat, 'Giant Growth', {'target_card_id': cid}))
    for index in (0, 1, 2):
        state = upgrade(state, seat, cid, index)
    assert effective_combat_stats(state, cid) == (12, 12)
    assert state.cards[cid].counters['+1/+1'] == 1
    state = cleanup(state)
    assert effective_combat_stats(state, cid) == (9, 9)
    assert set(effective_keywords(state, cid)) == {'flying', 'first strike'}


@pytest.mark.parametrize('seat', [1, 2])
def test_humility_response_then_later_upgrade_uses_shared_timestamp_layers(seat):
    state, ids, cid = position(seat)
    state = drain(cast(state, ids, seat, 'Leyline of Anticipation'))
    state = activate(upgrade(upgrade(state, seat, cid, 0), seat, cid, 1), seat, cid, 2)
    state = top(cast(state, ids, seat, 'Humility'))
    assert effective_combat_stats(state, cid) == (1, 1)
    assert effective_keywords(state, cid) == []
    state = drain(state)
    assert effective_combat_stats(state, cid) == (8, 8)
    assert set(effective_keywords(state, cid)) == {'flying', 'first strike'}


@pytest.mark.parametrize('seat', [1, 2])
def test_real_control_change_response_does_not_retarget_or_rewrite_owner(seat):
    state, ids, cid = position(seat)
    state = activate(state, seat, cid, 0)
    original = deepcopy(state.stack[-1])
    state = top(cast(state, ids, 3-seat, 'Ray of Command', {'target_card_id': cid}))
    assert state.cards[cid].owner == seat and state.cards[cid].controller == 3-seat
    assert state.stack[-1].id == original.id and state.stack[-1].controller == seat
    state = drain(state)
    assert effective_combat_stats(state, cid) == (2, 2)
    assert state.cards[cid].owner == seat and state.cards[cid].controller == 3-seat
    state = upgrade(state, 3-seat, cid, 1)
    assert effective_combat_stats(state, cid) == (4, 4)


@pytest.mark.parametrize('seat', [1, 2])
def test_real_flash_song_response_never_adds_creature_and_latent_stats_survive_until_restored(seat):
    state, ids, cid = position(seat)
    state = drain(cast(state, ids, seat, 'Leyline of Anticipation'))
    state = drain(cast(state, ids, seat, 'Battlegrowth', {'target_card_id': cid}))
    state = activate(state, seat, cid, 0)
    pending = state.stack[-1].id
    state = top(cast(state, ids, seat, 'Song of the Dryads', {'target_card_id': cid}))
    assert [item.id for item in state.stack] == [pending]
    assert set(effective_types(state, cid)) == {'Land'}
    assert effective_type_line(state, state.cards[cid]) == 'Land \u2014 Forest'
    state = drain(state)
    assert set(effective_types(state, cid)) == {'Land'}
    assert effective_type_line(state, state.cards[cid]) == 'Land \u2014 Forest'
    assert state.cards[cid].counters['+1/+1'] == 1
    assert state.cards[cid].base_stat_effects[-1]['power'] == 2
    assert all(effect['types'] == [] for effect in state.cards[cid].type_effects)
    state = drain(cast(state, ids, seat, 'Naturalize', {'target_card_id': ids[seat]['Song of the Dryads']}))
    assert state.cards[ids[seat]['Song of the Dryads']].zone == Zone.GRAVEYARD
    assert set(effective_types(state, cid)) == {'Creature'}
    assert creature_types(state.cards[cid], state) == {'kithkin', 'spirit'}
    assert effective_combat_stats(state, cid) == (3, 3)
    assert_physical(state.cards[cid])


@pytest.mark.parametrize('subtypes', [None, [], ['spirit']])
def test_native_subtype_only_overlay_preserves_empty_default_noop_and_never_adds_types(subtypes):
    state, ids, cid = position(1)
    before = snapshot(state)
    add_type_effect(state, cid, [], creature_subtypes=subtypes)
    assert set(effective_types(state, cid)) == {'Creature'}
    if subtypes is None:
        assert snapshot(state) == before
    else:
        assert creature_types(state.cards[cid], state) == set(subtypes)
        assert state.cards[cid].type_effects[-1]['types'] == []
        assert_physical(state.cards[cid])


@pytest.mark.parametrize('body', [
    'This creature becomes a Kithkin Spirit with base power and toughness 2/2. Draw a card.',
    'This creature becomes a Kithkin Spirit with base power and toughness 2/2 (then draw a card).',
    'This creature becomes a Kithkin Spirit (draw a card) with base power and toughness 2/2.',
    'This creature becomes a Kithkin Spirit with base power and toughness 2/2; then draw a card.',
    'This creature becomes a Kithkin Spirit with base power and toughness 2/2. This creature becomes a Kithkin Spirit with base power and toughness 2/2.',
    'If you control an Island, this creature becomes a Kithkin Spirit with base power and toughness 2/2.',
    'This creature becomes a Kithkin Unknownsubtype with base power and toughness 2/2.',
    'This creature becomes a Kithkin Spirit with base power and toughness 2/2, flying, and draw a card.',
])
def test_noncard_unknown_or_partial_raw_bodies_never_admit_a_prefix_reward(body):
    state, ids, cid = position(1)
    proxy = replace(state.cards[cid], oracle_text=body, mana_cost='')
    before = snapshot(state)
    spec = build_ability_spec(state, proxy, 1, report_unsupported=False)
    assert spec.effect.key == 'noop'
    assert spec.effect.payload.get('__unsupported_instruction') == body.lower()
    assert snapshot(state) == before


@pytest.mark.parametrize('field,value', [
    ('source_incarnation', True), ('source_incarnation', 1.0),
    ('source_zone_change_sequence', False), ('source_zone_change_sequence', 1.0),
])
def test_noncard_malformed_source_reference_rejected_atomically_before_native_commit(field, value):
    state, ids, cid = position(1)
    state = activate(state, 1, cid, 0)
    state.stack[-1].payload[field] = value
    state = act(state, state.priority_player, {'type': 'pass_priority'})
    before = snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    assert snapshot(state) == before
