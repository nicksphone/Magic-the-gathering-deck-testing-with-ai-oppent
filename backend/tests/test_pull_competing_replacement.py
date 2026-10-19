"""Full canonical paid episodes; no runtime zone or pending fabrication."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest

from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import infer_effect_from_oracle, inspect_target_hints
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_selected_graveyard_reference import act, ref, restart, snap, raw_card, position
from tests.test_causal_graveyard_return import RAW
from tests.test_selected_graveyard_reference import ROWS, canonical

BASE = Path(__file__).parent / 'fixtures'
FINAL_BYTES = (BASE / 'pull_competing_replacement/final-judgment.json').read_bytes()
assert hashlib.sha256(FINAL_BYTES).hexdigest() == '0bc8a7a902fcfe58169a1e26f71785c730dccac3c616717aa65b1b1621789875'
FINAL = json.loads(FINAL_BYTES)
UNMAKE = canonical('pull_competing_replacement/unmake.json',
    '02c4c2b38f5a6e270888f5949b1a0222151c558ee08bf115ddf1844619e641c1')
FORETELL = canonical('pull_competing_replacement/saw-it-coming.json',
    '79de7753c033d13ada37955f3593d0d234275ebad77c1309f2f56dbd3d98b5b0')
TWINS = canonical('announced_target_references/twincast.json',
    '12662d131d174e48af42758b9e8fd3b38ce6701d2de7d88217a527062786014f')
COLOSSUS = canonical('graveyard_inventory_audit/darksteel-colossus.json',
    '29cbb3f95182d047118c53af3626f1d551ac18ba82835676961376d75f54b8c5')
RIP_ROWS = (BASE / 'self_graveyard_interactions/canonical.jsonl').read_bytes()
assert hashlib.sha256(RIP_ROWS).hexdigest() == 'c9aa89aa5b1e6635489acac101f2d6824fa26867208849a04a80cb6d6c2e1b24'
RIP = next(row for row in map(json.loads, RIP_ROWS.splitlines()) if row['name'] == 'Rest in Peace')


def prepare(seat, route='final', copies=False):
    state, _ = position(seat, 'Torrential Gearhulk')
    state.step = Step.PRECOMBAT_MAIN
    col = raw_card(state, COLOSSUS, seat, Zone.HAND)
    final = raw_card(state, FINAL if route == 'final' else UNMAKE, seat, Zone.HAND)
    rip = raw_card(state, RIP, seat, Zone.HAND)
    pull = raw_card(state, RAW['Pull from Eternity'], 3-seat, Zone.HAND)
    twin = raw_card(state, TWINS, 3-seat, Zone.HAND)
    counter = raw_card(state, ROWS['Counterspell'], seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 18, 'W': 4, 'U': 2}
    state.players[3-seat].mana_pool = {'W': 2, 'U': 2}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': col.id})
    assert resolve_top_of_stack(state)
    assert state.cards[col.id].zone == Zone.BATTLEFIELD
    before = ref(state.cards[col.id])
    targets = {} if route == 'final' else {'target_card_id': col.id}
    key, payload = infer_effect_from_oracle(state, state.cards[final.id], seat, targets)
    expected = ('exile_all_creatures', {}) if route == 'final' else ('exile', targets)
    assert (key, payload) == expected, 'Lawful upstream exile body incomplete'
    state = act(state, seat, {'type': 'cast_spell', 'card_id': final.id, 'targets': targets})
    assert resolve_top_of_stack(state)
    assert state.cards[col.id].zone == Zone.EXILE
    assert ref(state.cards[col.id]) != before
    assert col.id in state.players[seat].exile
    result = state, col.id, rip.id, pull.id
    return (*result, twin.id, counter.id, final.id) if copies else result


def pause(seat):
    state, col, rip, pull = prepare(seat, route='unmake')
    state = act(state, seat, {'type': 'cast_spell', 'card_id': rip})
    assert resolve_top_of_stack(state)
    while state.stack:
        assert resolve_top_of_stack(state)
    state = act(state, seat, {'type': 'pass_priority'})
    assert state.priority_player == 3-seat
    state = act(state, 3-seat, {'type': 'cast_spell', 'card_id': pull,
                             'targets': {'target_card_id': col}})
    source_ref = ref(state.cards[pull])
    target_ref = ref(state.cards[col])
    assert not resolve_top_of_stack(state)
    pending = state.pending_replacement_choice
    assert pending['resume_kind'] == 'exile_graveyard_entry'
    assert pending['player_id'] == seat != 3-seat
    assert {option['source_id'] for option in pending['options']} == {col, rip}
    assert state.cards[pull].zone == Zone.STACK
    assert ref(state.cards[col]) == target_ref
    assert ref(state.cards[pull]) == source_ref
    return restart(state), col, rip, pull


def record(state):
    name = hashlib.sha256(os.environ['PYTEST_CURRENT_TEST'].encode()).hexdigest()[:16]
    with (Path(os.environ['MTG_PULL_EVIDENCE']) / (name + '.json')).open('x') as out:
        json.dump(snap(state), out, indent=2)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_lawful_exile_upstream(seat):
    state, col, _, _ = prepare(seat)
    assert state.cards[col].zone == Zone.EXILE
    assert state.players[seat].mana_pool['C'] == 3
    assert state.players[seat].mana_pool['W'] == 2
    record(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_unmake_exile_upstream(seat):
    state, col, _, _ = prepare(seat, route='unmake')
    assert state.cards[col].zone == Zone.EXILE
    assert state.players[seat].mana_pool['C'] == 7
    assert state.players[seat].mana_pool['W'] == 1
    record(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('winner', ['library', 'exile'])
def test_actual_paid_competing_owner_choice_restores_and_finishes_frame(seat, winner):
    state, col, rip, pull = pause(seat)
    pending = deepcopy(state.pending_replacement_choice)
    chosen = col if winner == 'library' else rip
    assert len(RulesEngine().legal_moves(state, seat)) == 2
    assert RulesEngine().legal_moves(state, 3-seat) == []
    state = act(state, seat, {'type': 'choose_replacement', 'replacement_source_id': chosen})
    assert state.pending_replacement_choice is None
    assert state.cards[col].zone == (Zone.LIBRARY if winner == 'library' else Zone.EXILE)
    assert col in getattr(state.players[seat], winner)
    assert state.cards[pull].zone == Zone.EXILE  # RIP replaces the real spell's own finish.
    assert not any(item.id == pending['resolving_item']['id'] for item in state.stack)
    assert not state.trigger_staging
    state = restart(state)
    before = snap(state)
    with pytest.raises(ActionRejected):
        act(state, seat, {'type': 'choose_replacement', 'replacement_source_id': chosen})
    assert snap(state) == before
    record(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['wrong-actor', 'unoffered', 'null-frame', 'changed-frame',
    'target-reference', 'source-reference', 'candidate-source', 'duplicate-options', 'context-extra'])
def test_actual_pending_rejects_invalid_context_without_root_mutation(seat, bad):
    state, col, _, _ = pause(seat)
    pending = state.pending_replacement_choice
    context = pending['exile_graveyard_context']
    # Corrupt native persisted context only; these are NOT causal zone-transition episodes.
    actor, chosen = seat, col
    if bad == 'wrong-actor': actor = 3-seat
    elif bad == 'unoffered': chosen = 'not-an-offered-source'
    elif bad == 'null-frame': pending['resolving_item'] = None
    elif bad == 'changed-frame': pending['resolving_item']['id'] = 'different-frame'
    elif bad == 'target-reference': context['target_references']['targets']['target_card_id']['zone_change_sequence'] += 1
    elif bad == 'source-reference': context['physical_source_reference']['zone_change_sequence'] += 1
    elif bad == 'candidate-source': context['candidates'][col]['source_sequence'] += 1
    elif bad == 'duplicate-options': pending['options'].append(deepcopy(pending['options'][0]))
    else: context['unknown'] = True
    before = snap(state)
    with pytest.raises(ActionRejected):
        act(state, actor, {'type': 'choose_replacement', 'replacement_source_id': chosen})
    assert snap(state) == before
    record(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('choice', ['keep', 'new'])
@pytest.mark.parametrize('counter_original', [False, True])
def test_paid_pull_copy_keep_retarget_and_departed_original_source(seat, choice, counter_original):
    state, col, rip, pull, twin, counter, exiler = prepare(seat, 'unmake', copies=True)
    state = act(state, seat, {'type': 'cast_spell', 'card_id': rip})
    assert resolve_top_of_stack(state)
    while state.stack:
        assert resolve_top_of_stack(state)
    assert state.cards[exiler].zone == Zone.EXILE
    state = act(state, seat, {'type': 'pass_priority'})
    state = act(state, 3-seat, {'type': 'cast_spell', 'card_id': pull,
                             'targets': {'target_card_id': col}})
    original = state.stack[-1].id
    seal = deepcopy(state.stack[-1].payload['__announced_target_references'])
    state = act(state, 3-seat, {'type': 'cast_spell', 'card_id': twin,
                             'targets': {'target_stack_id': original}})
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice['kind'] == 'copy_target'
    copied_id = state.pending_mechanic_choice['stack_id']
    state = restart(state)
    state = act(state, 3-seat, {'type': 'choose_mechanic', 'card_ids': [
        'keep' if choice == 'keep' else 'target_card_id:' + exiler]})
    copied = next(item for item in state.stack if item.id == copied_id)
    selected = col if choice == 'keep' else exiler
    assert copied.payload['target_card_id'] == selected
    refs = copied.payload['__announced_target_references']
    assert refs['targets']['target_card_id']['card_id'] == selected
    if choice == 'keep': assert refs == seal
    if counter_original:
        if state.priority_player != seat:
            state = act(state, state.priority_player, {'type': 'pass_priority'})
        state = act(state, seat, {'type': 'cast_spell', 'card_id': counter,
                                 'targets': {'target_stack_id': original}})
        assert resolve_top_of_stack(state)
        assert state.cards[pull].zone == Zone.EXILE
        assert not any(item.id == original for item in state.stack)
    state = restart(state)
    if choice == 'keep':
        assert not resolve_top_of_stack(state)
        pending = state.pending_replacement_choice
        assert pending['exile_graveyard_context']['source_kind'] == 'copied_spell'
        assert pending['exile_graveyard_context']['physical_source_reference'] is None
        state = act(restart(state), seat, {'type': 'choose_replacement',
                                         'replacement_source_id': col})
        assert state.cards[col].zone == Zone.LIBRARY
    else:
        assert resolve_top_of_stack(state)
        assert state.cards[exiler].zone == Zone.EXILE
    assert not any(item.id == copied_id for item in state.stack)
    record(restart(state))


@pytest.mark.parametrize('seat', [1, 2])
def test_native_committed_graveyard_receipt_and_no_false_death(seat, monkeypatch):
    from tests.test_causal_graveyard_return import exile_selected, respond
    import rules_engine.events as events
    state, _, target, _, spells, _, old = exile_selected(seat)
    receipts = []
    original = events._collect_triggers
    def observe(state, event, payload):
        receipts.append((event, deepcopy(payload)))
        return original(state, event, payload)
    monkeypatch.setattr(events, '_collect_triggers', observe)
    state = respond(state, 3-seat, spells['Pull from Eternity'], target)
    source_ref = ref(state.cards[target])
    assert resolve_top_of_stack(state)
    entry = [data for event, data in receipts if event == 'enters_graveyard' and data['card_id'] == target]
    assert len(entry) == 1
    assert entry[0]['owner'] == seat
    assert entry[0]['from_zone'] == 'exile'
    assert entry[0]['previous_reference'] == {'incarnation': source_ref[0], 'zone_change_sequence': source_ref[1]}
    assert entry[0]['entry_reference'] == {'incarnation': ref(state.cards[target])[0],
                                         'zone_change_sequence': ref(state.cards[target])[1]}
    assert ref(state.cards[target]) != old
    assert not any(event in {'leaves_battlefield', 'creature_dies', 'permanent_dies'} and data.get('card_id') == target
                   for event, data in receipts)
    record(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_native_whole_view_and_typed_owner_choice(seat):
    from api_contracts import ReplacementChoice
    from game_state.serializers import serialize_match
    from pydantic import ValidationError
    from training.environment import TrainingEnvironment
    state, col, _, _ = pause(seat)
    before = snap(state)
    public = serialize_match(state)
    assert public['pending_replacement_choice'] == state.pending_replacement_choice
    pending = state.pending_replacement_choice
    context = pending['exile_graveyard_context']
    assert context['resolving_frame'] == pending['resolving_item']
    assert context['target_references'] == pending['resolving_item']['payload']['__announced_target_references']
    assert context['source_kind'] == 'physical_spell'
    source = state.cards[pending['resolving_item']['source_card_id']]
    assert context['physical_source_reference'] == {
        'incarnation': ref(source)[0], 'zone_change_sequence': ref(source)[1]}
    hidden = {cid for player in state.players.values() for cid in player.hand + player.library}
    encoded = json.dumps(pending)
    assert all(cid not in encoded for cid in hidden)
    moves = RulesEngine().legal_moves(state, seat)
    assert {move['replacement_source_id'] for move in moves} == {
        option['source_id'] for option in state.pending_replacement_choice['options']}
    assert RulesEngine().legal_moves(state, 3-seat) == []
    assert snap(state) == before
    env = TrainingEnvironment()
    env._state = deepcopy(state)
    for move in moves:
        with pytest.raises(ValidationError):
            ReplacementChoice.model_validate(move)
        materialized = env.lookup_intent(move, seat)['action']
        typed = ReplacementChoice.model_validate(materialized)
        assert typed.replacement_source_id == move['replacement_source_id']
        assert snap(env._state) == before
    with pytest.raises(ValidationError):
        ReplacementChoice.model_validate({**moves[0], 'exile_graveyard_context':
            state.pending_replacement_choice['exile_graveyard_context']})
    state = act(restart(state), seat,
        ReplacementChoice.model_validate({'type': 'choose_replacement',
            'replacement_source_id': col}).model_dump(exclude_none=True))
    assert state.cards[col].zone == Zone.LIBRARY
    record(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('fault', ['copy-kind-null', 'snapshot-null', 'unhashable-type'])
def test_native_copied_pending_malformed_source_is_atomic(seat, fault):
    state, col, rip, pull, twin, _, _ = prepare(seat, 'unmake', copies=True)
    state = act(state, seat, {'type': 'cast_spell', 'card_id': rip})
    assert resolve_top_of_stack(state)
    while state.stack:
        assert resolve_top_of_stack(state)
    state = act(state, seat, {'type': 'pass_priority'})
    state = act(state, 3-seat, {'type': 'cast_spell', 'card_id': pull,
                             'targets': {'target_card_id': col}})
    state = act(state, 3-seat, {'type': 'cast_spell', 'card_id': twin,
                             'targets': {'target_stack_id': state.stack[-1].id}})
    assert not resolve_top_of_stack(state)
    state = act(restart(state), 3-seat, {'type': 'choose_mechanic', 'card_ids': ['keep']})
    assert not resolve_top_of_stack(state)
    pending = state.pending_replacement_choice
    # Persisted-context corruption probe, not a causal zone-transition claim.
    for frame in (pending['resolving_item'],
                  pending['exile_graveyard_context']['resolving_frame']):
        payload = frame['payload']
        if fault == 'copy-kind-null': payload['__stack_copy_kind'] = None
        elif fault == 'snapshot-null': payload['__copied_card'] = None
        else: payload['__copied_card']['types'] = [{'unhashable': True}]
    state = restart(state)
    before = snap(state)
    with pytest.raises(ActionRejected):
        act(state, seat, {'type': 'choose_replacement', 'replacement_source_id': col})
    assert snap(state) == before
    record(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_foretell_face_down_exile_is_not_a_pull_target(seat):
    from game_state.serializers import serialize_match
    state, _ = position(seat, 'Torrential Gearhulk')
    state.step = Step.PRECOMBAT_MAIN
    hidden = raw_card(state, FORETELL, seat, Zone.HAND)
    pull = raw_card(state, RAW['Pull from Eternity'], 3-seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 2}
    state.players[3-seat].mana_pool = {'W': 1}
    state = act(state, seat, {'type': 'foretell', 'card_id': hidden.id})
    assert state.cards[hidden.id].zone == Zone.EXILE
    assert state.cards[hidden.id].exile_face_down
    assert sum(state.players[seat].mana_pool.values()) == 0
    state = act(restart(state), seat, {'type': 'pass_priority'})
    before = snap(state)
    hints = inspect_target_hints(state, state.cards[pull.id], 3-seat)
    assert hints['exile_card_targets'] == []
    assert hidden.id not in json.dumps(hints)
    assert not serialize_match(state)['players'][seat]['exile']
    with pytest.raises(ActionRejected):
        act(state, 3-seat, {'type': 'cast_spell', 'card_id': pull.id,
                          'targets': {'target_card_id': hidden.id}})
    assert snap(state) == before
    record(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['missing', 'null', 'plural', 'distribution', 'player'])
def test_actual_face_up_target_requires_exact_scalar_request(seat, bad):
    state, col, _, pull = prepare(seat, route='unmake')
    state = act(state, seat, {'type': 'pass_priority'})
    targets = {'target_card_id': col}
    if bad == 'missing': targets = {}
    elif bad == 'null': targets['target_card_id'] = None
    elif bad == 'plural': targets['target_card_ids'] = [col]
    elif bad == 'distribution': targets['target_distribution'] = {col: 1}
    else: targets['target_player'] = seat
    before = snap(state)
    with pytest.raises(ActionRejected):
        act(state, 3-seat, {'type': 'cast_spell', 'card_id': pull, 'targets': targets})
    assert snap(state) == before
    record(state)
