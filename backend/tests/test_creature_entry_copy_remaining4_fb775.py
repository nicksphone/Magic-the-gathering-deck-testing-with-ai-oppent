"""Full-RAW births and actual paid copy entry, with labeled protocol negatives."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from card_data.sync import ScryfallSyncService
from game_state.serializers import deserialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.continuous import effective_combat_stats, effective_keywords
from rules_engine.engine import RulesEngine
from rules_engine.entry_copy import PLAN, compile_instruction, plan_matches
from rules_engine.printed_body import printed_body_gaps
from rules_engine.type_effects import effective_types
from tests.test_self_creature_change_fb775 import (
    act, all_three, assert_physical, cast, drain, snapshot, upgrade)


BACKEND = Path(__file__).resolve().parents[1]
SOURCE = BACKEND / 'tests/fixtures/figure_remaining4_fb775/SOURCES.json'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == 'f7a6bacb96d028e4c05ad22608a87a63a8d2ee6a8cb8df9974153d27f3772a8b'
SOURCES = json.loads(SOURCE.read_bytes())


def raw(name):
    pin = SOURCES[name]
    body = (BACKEND / pin['file']).read_bytes()
    assert hashlib.sha256(body).hexdigest() == pin['sha256']
    obj = json.loads(body.splitlines()[pin['line']-1] if pin['line'] else body)
    for part in pin['steps']:
        obj = obj[part]
    assert obj['object'] == 'card' and obj['name'] == name and len(obj) == pin['fields'] >= 60
    assert obj['id'] == pin['id'] and obj['oracle_id'] == pin['oracle_id']
    assert hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'),
                                   ensure_ascii=False).encode()).hexdigest() == pin['row_sha256']
    return obj


def position(seat):
    rows = []
    for name in SOURCES:
        obj = raw(name)
        normalized = ScryfallSyncService._normalize_payload(
            obj, ScryfallSyncService._extract_remote_image_uri(obj))
        rows.append({**obj, **normalized, 'card_name': name,
            'quantity': 61-len(SOURCES) if name == 'Forest' else 1,
            'card_faces': json.loads(normalized['card_faces_json']), 'colors': obj['colors']})
    state = MatchFactory.from_decks(deepcopy(rows), deepcopy(rows), seed=8437)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.turn = 5
    state.priority_stops = {pid: set(Step) for pid in (1, 2)}
    ids = {1: {}, 2: {}}
    for pid, player in state.players.items():
        player.mana_pool = dict(W=30, U=30, B=10, R=10, G=30, C=40)
        for name in SOURCES:
            if name == 'Forest':
                continue
            cid = next(cid for cid in player.hand + player.library if state.cards[cid].name == name)
            ids[pid][name] = cid
            if cid in player.library:
                player.library.remove(cid)
                player.hand.append(cid)
                state.cards[cid].move_to_zone(Zone.HAND)
    state.active_player = state.priority_player = seat
    return state, ids


def permanent(state, ids, seat, name):
    # Constructed main-phase turn pose; the card is then genuinely paid/cast/resolved.
    state.active_player = state.priority_player = seat
    return drain(cast(state, ids, seat, name))


def pending_copy(state, ids, seat, name='Clone'):
    state.active_player = state.priority_player = seat
    state = cast(state, ids, seat, name)
    cid = ids[seat][name]
    frame = next(item for item in state.stack if item.source_card_id == cid)
    state = drain(state)
    pending = state.pending_mechanic_choice
    assert pending and pending['kind'] == 'entry_copy' and pending['player_id'] == seat
    assert state.cards[cid].zone == Zone.STACK
    assert pending['effect_payload'][PLAN]['frame']['id'] == frame.id
    assert pending['effect_payload'][PLAN]['entries'][0]['clause'] == raw(name)['oracle_text']
    assert pending['resolving_item']['source_card_id'] == cid
    assert plan_matches(state, pending['effect_payload'])
    return state, cid


def select(state, seat, cid):
    state = deserialize_match_snapshot(snapshot(state))
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': [cid]})
    state = drain(state)
    assert not state.pending_mechanic_choice and not state.stack
    return state


@pytest.mark.parametrize('name', ['Clone', 'Sculpting Steel'])
def test_full_raw_complete_admission_agrees_with_existing_printed_body_delegate(name):
    state, ids = position(1)
    cid = ids[1][name]
    before = snapshot(state)
    assert compile_instruction(raw(name)['oracle_text']) == raw(name)['oracle_text']
    assert not printed_body_gaps(state.cards[cid])
    assert snapshot(state) == before


@pytest.mark.parametrize('body', [
    'You may have this creature enter as a copy of any creature on the battlefield. (Then draw a card.)',
    'You may have this creature enter as a copy of any creature on the battlefield. Draw a card.',
    'You may have this creature enter as a copy of any artifact or creature on the battlefield.',
    'If you control an Island, you may have this creature enter as a copy of any creature on the battlefield.',
])
def test_noncard_unknown_complete_copy_bodies_reject_instead_of_admitting_prefix(body):
    with pytest.raises(ActionRejected):
        compile_instruction(body)


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_clone_exact_current_roster_retained_one_one_and_own_ability_binding(seat):
    state, ids = position(seat)
    state = permanent(state, ids, 3-seat, 'Figure of Destiny')
    target = ids[3-seat]['Figure of Destiny']
    state = all_three(state, 3-seat, target)
    state = permanent(state, ids, seat, 'Sol Ring')
    state = permanent(state, ids, seat, 'Figure of Destiny')
    coated = ids[seat]['Figure of Destiny']
    state = permanent(state, ids, seat, 'Liquimetal Coating')
    state = act(state, seat, {'type': 'activate_ability', 'card_id': ids[seat]['Liquimetal Coating'],
                            'ability_index': 0, 'targets': {'target_card_id': coated}})
    state = drain(state)
    assert set(effective_types(state, coated)) == {'Artifact', 'Creature'}
    state, clone = pending_copy(state, ids, seat)
    assert set(state.pending_mechanic_choice['options']) == {target, coated}
    assert ids[seat]['Sol Ring'] not in state.pending_mechanic_choice['options']
    before = snapshot(state)
    assert plan_matches(state, state.pending_mechanic_choice['effect_payload'])
    assert snapshot(state) == before
    state = select(state, seat, target)
    assert state.cards[clone].owner == state.cards[clone].controller == seat
    assert state.cards[target].owner == 3-seat
    assert effective_combat_stats(state, clone) == (1, 1)
    assert effective_keywords(state, clone) == []
    assert_physical(state.cards[clone], 'Clone')
    state = upgrade(state, seat, clone, 0)
    assert effective_combat_stats(state, clone) == (2, 2)
    assert effective_combat_stats(state, target) == (8, 8)
    assert state.cards[clone].type_effects[-1]['source_card_id'] == clone
    assert set(effective_keywords(state, target)) == {'flying', 'first strike'}


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_clone_decline_is_real_zero_zero_and_not_kept_alive_by_invented_stats(seat):
    state, ids = position(seat)
    state, clone = pending_copy(state, ids, seat)
    state = act(deserialize_match_snapshot(snapshot(state)), seat,
                {'type': 'choose_mechanic', 'card_ids': []})
    state = drain(state)
    assert state.cards[clone].zone == Zone.GRAVEYARD
    assert not state.pending_mechanic_choice and not state.stack
    assert state.cards[clone].name == 'Clone'
    assert not state.cards[clone].counters
    assert_physical(state.cards[clone], 'Clone')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mutation', ['source_incarnation', 'roster'])
def test_noncard_pending_clone_tamper_rejects_before_commit_and_preserves_root(seat, mutation):
    state, ids = position(seat)
    state = permanent(state, ids, seat, 'Figure of Destiny')
    state = permanent(state, ids, seat, 'Sol Ring')
    target = ids[seat]['Figure of Destiny']
    state, clone = pending_copy(state, ids, seat)
    pending = state.pending_mechanic_choice
    if mutation == 'source_incarnation':
        pending['effect_payload'][PLAN]['entries'][0]['reference']['incarnation'] += 1
    else:
        pending['options'] = [ids[seat]['Sol Ring']]
    before = snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': [target]})
    assert snapshot(state) == before
    assert state.cards[clone].zone == Zone.STACK


@pytest.mark.parametrize('seat', [1, 2])
def test_current_genuinely_animated_forest_is_eligible_but_animation_is_not_copied(seat):
    from tests.graveyard_batch_native_support_bf62 import place
    state, ids = position(seat)
    forest = place(state, 'Forest', Zone.BATTLEFIELD, seat)
    state = permanent(state, ids, seat, 'Nissa, Who Shakes the World')
    state = act(state, seat, {'type': 'activate_loyalty',
        'card_id': ids[seat]['Nissa, Who Shakes the World'], 'ability_index': 0,
        'targets': {'target_card_id': forest}})
    state = drain(state)
    assert {'Land', 'Creature'} <= set(effective_types(state, forest))
    assert effective_combat_stats(state, forest) == (3, 3)
    state, clone = pending_copy(state, ids, seat)
    assert forest in state.pending_mechanic_choice['options']
    state = select(state, seat, forest)
    assert state.cards[clone].zone == Zone.BATTLEFIELD
    assert set(effective_types(state, clone)) == {'Land'}
    assert not state.cards[clone].counters and not state.cards[clone].type_effects
    assert state.cards[clone].characteristic_record['values']['name'] == 'Forest'
    assert state.cards[clone].characteristic_record['physical']['name'] == 'Clone'
    assert state.cards[clone].owner == state.cards[clone].controller == seat
    assert effective_combat_stats(state, forest) == (3, 3)


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_creature_copy_of_actual_copy_uses_retained_values_not_physical_clone(seat):
    state, ids = position(seat)
    state = permanent(state, ids, seat, 'Figure of Destiny')
    figure = ids[seat]['Figure of Destiny']
    state = all_three(state, seat, figure)
    state, first = pending_copy(state, ids, seat)
    state = select(state, seat, figure)
    state, second = pending_copy(state, ids, 3-seat)
    assert first in state.pending_mechanic_choice['options']
    state = select(state, 3-seat, first)
    assert effective_combat_stats(state, first) == effective_combat_stats(state, second) == (1, 1)
    assert state.cards[first].characteristic_record['values'] == state.cards[second].characteristic_record['values']
    assert state.cards[first].owner == seat and state.cards[second].owner == 3-seat
    assert_physical(state.cards[first], 'Clone')
    assert_physical(state.cards[second], 'Clone')
    assert effective_combat_stats(state, figure) == (8, 8)


@pytest.mark.parametrize('seat', [1, 2])
def test_artifact_copy_keeps_exact_saved_clause_roster_and_physical_identity(seat):
    state, ids = position(seat)
    state = permanent(state, ids, seat, 'Figure of Destiny')
    state = permanent(state, ids, 3-seat, 'Sol Ring')
    target = ids[3-seat]['Sol Ring']
    state, steel = pending_copy(state, ids, seat, 'Sculpting Steel')
    assert state.pending_mechanic_choice['options'] == [target]
    state = select(state, seat, target)
    assert state.cards[steel].name == 'Sol Ring'
    assert state.cards[steel].oracle_text == raw('Sol Ring')['oracle_text']
    assert state.cards[steel].characteristic_record['physical']['name'] == 'Sculpting Steel'
    assert state.cards[steel].owner == state.cards[steel].controller == seat
    assert ids[seat]['Figure of Destiny'] not in state.players[seat].graveyard
