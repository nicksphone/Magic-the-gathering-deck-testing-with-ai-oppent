"""Full canonical modal casts reject fabricated recipients before any payment."""
from copy import deepcopy
import pickle

import pytest

from api_contracts import CastAction, ModeTarget
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.ability_model import build_spell_spec
from rules_engine.cast_choice import validate_mode_targets
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import _infer_closed_damage_instruction
from tests.spell_admission_safety_support import add
from tests.test_incendiary_modal_root import MODES, RAW, announced, position, reload


FIELDS = tuple(ModeTarget.model_fields)
LOCATIONS = ('broadcast', 'wheel', 'outer')


def phantom_packet(seat, field, location, *, mixed=False):
    index = 1 if location == 'broadcast' else 3
    pair = (0, index) if mixed else (1, 3)
    targets = announced(seat, pair)
    value = {'target_player': 3-seat, 'target_card_id': 'nonbasic',
             'target_stack_id': 'declared-fabricated-stack'}[field]
    packet = targets if location == 'outer' else targets['mode_targets'][MODES[index]]
    packet[field] = value
    if location == 'outer':
        del targets['mode_targets']
    return targets


def action_for(source, targets, wire):
    action = {'type': 'cast_spell', 'card_id': source.id, 'targets': targets}
    if wire == 'typed':
        return CastAction.model_validate(action).model_dump(exclude_none=True)
    assert wire == 'raw'
    # Even raw negatives are syntactically valid public packets. The printed
    # branch requirement, not schema type rejection, must stop the cast.
    CastAction.model_validate(action)
    return action


def pass_priority(state, seat):
    assert state.priority_player == seat
    return checked_action(reload(state), RulesEngine(), seat, {'type': 'pass_priority'})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field', FIELDS)
@pytest.mark.parametrize('location', LOCATIONS)
@pytest.mark.parametrize('wire', ['typed', 'raw'])
def test_targetless_public_cast_rejects_fabricated_recipient_before_payment_root_atomic(seat, field, location, wire):
    state, source = position(seat)
    targets = phantom_packet(seat, field, location)
    action = action_for(source, targets, wire)
    before = pickle.dumps(state)
    reason = 'Unsupported spell resolution' if location == 'outer' else 'has no targets'
    if field == 'target_stack_id':
        reason = 'Target stack item is unavailable' if location == 'outer' else 'Mode stack target is unavailable'
    with pytest.raises(ActionRejected, match=reason):
        checked_action(state, RulesEngine(), seat, action)
    assert pickle.dumps(state) == before
    assert state.cards[source.id].zone == Zone.HAND and not state.stack
    assert state.players[seat].mana_pool == {'R': 2, 'C': 3}
    assert source.oracle_text == RAW['oracle_text']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field', FIELDS)
@pytest.mark.parametrize('location', LOCATIONS)
def test_native_mode_validator_rejects_targetless_recipient_without_compile_or_payment(seat, field, location):
    state, source = position(seat)
    targets = phantom_packet(seat, field, location)
    if location == 'outer':
        # The external cast has an earlier shared/per-mode exclusivity gate.
        # The public native validator must also fence its own outer seam.
        targets['mode_targets'] = announced(seat, (1, 3))['mode_targets']
    before = pickle.dumps(state)
    valid, reason = validate_mode_targets(state, source, seat, targets)
    assert not valid and reason
    assert pickle.dumps(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field', FIELDS)
@pytest.mark.parametrize('location', LOCATIONS)
def test_complete_compiler_rejects_targetless_recipient_before_lowering(seat, field, location):
    state, source = position(seat)
    before = pickle.dumps(state)
    key, payload = _infer_closed_damage_instruction(source.oracle_text, source.name,
                                                     phantom_packet(seat, field, location))
    assert key == 'noop' and payload['__unsupported_instruction'] == RAW['oracle_text']
    assert pickle.dumps(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field', FIELDS)
@pytest.mark.parametrize('location', ['broadcast', 'wheel'])
def test_real_targeted_sibling_does_not_authorize_phantom_on_targetless_branch(seat, field, location):
    state, source = position(seat)
    targets = phantom_packet(seat, field, location, mixed=True)
    before = pickle.dumps(state)
    reason = 'Mode stack target is unavailable' if field == 'target_stack_id' else 'has no targets'
    with pytest.raises(ActionRejected, match=reason):
        checked_action(state, RulesEngine(), seat, action_for(source, targets, 'typed'))
    assert pickle.dumps(state) == before
    key, payload = _infer_closed_damage_instruction(source.oracle_text, source.name, targets)
    assert key == 'noop' and payload['__unsupported_instruction'] == RAW['oracle_text']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field', FIELDS)
@pytest.mark.parametrize('index', [1, 3])
def test_internal_single_mode_probe_still_binds_targetless_printed_branch(seat, field, index):
    targets = {'mode_text': MODES[index], field: phantom_packet(seat, field, 'outer')[field]}
    key, payload = _infer_closed_damage_instruction(RAW['oracle_text'], RAW['name'], targets)
    assert key == 'noop' and payload['__unsupported_instruction'] == RAW['oracle_text']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field', ['target_card_ids', 'target_distribution'])
@pytest.mark.parametrize('wire', ['typed', 'raw'])
def test_targetless_outer_target_collections_reject_before_payment(seat, field, wire):
    state, source = position(seat)
    targets = announced(seat, (1, 3))
    del targets['mode_targets']
    targets[field] = ['nonbasic'] if field == 'target_card_ids' else {'nonbasic': 1}
    before = pickle.dumps(state)
    with pytest.raises(ActionRejected, match='Unsupported spell resolution'):
        checked_action(state, RulesEngine(), seat, action_for(source, targets, wire))
    assert pickle.dumps(state) == before
    native = {**targets, 'mode_targets': announced(seat, (1, 3))['mode_targets']}
    assert not validate_mode_targets(state, source, seat, native)[0]
    key, payload = _infer_closed_damage_instruction(source.oracle_text, source.name, targets)
    assert key == 'noop' and payload['__unsupported_instruction'] == RAW['oracle_text']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('wire', ['typed', 'raw'])
@pytest.mark.parametrize('shared', [False, True])
def test_nullable_public_mode_defaults_are_not_fabricated_targets_and_paid_modes_resolve(seat, wire, shared):
    state, source = position(seat)
    targets = announced(seat, (1, 3))
    for mode in targets['mode_targets']:
        targets['mode_targets'][mode] = ModeTarget().model_dump()
    targets.update({field: None for field in FIELDS})
    empty_collections = {**targets, 'target_card_ids': [], 'target_distribution': {}}
    valid, reason = validate_mode_targets(state, source, seat, empty_collections)
    assert valid, reason
    key, payload = _infer_closed_damage_instruction(source.oracle_text, source.name, empty_collections)
    assert key == 'effect_sequence'
    assert [effect['effect_key'] for effect in payload['effects']] == ['damage_each_creature', 'each_player_discard']
    if shared:
        del targets['mode_targets']
    hands = {pid: set(player.hand) - {source.id} for pid, player in state.players.items()}
    state = checked_action(state, RulesEngine(), seat, action_for(source, targets, wire))
    assert state.cards[source.id].zone == Zone.STACK and not any(state.players[seat].mana_pool.values())
    frame = deepcopy(state.stack[-1])
    assert frame.targets == []
    for effect in frame.payload['effects']:
        assert all(effect['payload'].get(field) is None for field in FIELDS)
    state = pass_priority(state, seat)
    assert state.stack[-1].id == frame.id and state.priority_player == 3-seat
    state = pass_priority(state, 3-seat)
    assert not state.stack and state.cards[source.id].zone == Zone.GRAVEYARD
    for pid in (1, 2):
        assert state.cards[f'creature-{pid}'].counters['__damage_marked'] == 2
        assert all(state.cards[cid].zone == Zone.GRAVEYARD for cid in hands[pid])
        assert len(state.players[pid].hand) == len(hands[pid])
    assert state.discards_this_turn == {pid: len(hand) for pid, hand in hands.items()}
    reload(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('wire', ['typed', 'raw'])
@pytest.mark.parametrize('pair', [(0, 1), (0, 3), (1, 2), (2, 3)])
def test_shared_target_for_real_sibling_preserves_paid_targetless_branch(seat, wire, pair):
    state, source = position(seat)
    targets = {'mode_texts': [MODES[index] for index in reversed(pair)]}
    targets.update({'target_player': 3-seat} if 0 in pair else {'target_card_id': 'nonbasic'})
    before = pickle.dumps(state)
    hands = {pid: set(player.hand) - {source.id} for pid, player in state.players.items()}
    spec = build_spell_spec(state, source, seat, targets, report_unsupported=False)
    assert not spec.unsupported_resolution
    assert pickle.dumps(state) == before
    state = checked_action(state, RulesEngine(), seat, action_for(source, targets, wire))
    assert pickle.dumps(state) != before
    assert not any(state.players[seat].mana_pool.values())
    frame = deepcopy(state.stack[-1])
    assert frame.controller == seat and frame.source_card_id == source.id
    assert frame.payload['mana_spent'] == 5
    assert [effect['mode_text'] for effect in frame.payload['effects']] == [MODES[index] for index in pair]
    for effect in frame.payload['effects']:
        if effect['effect_key'] in {'damage_each_creature', 'each_player_discard'}:
            assert all(effect['payload'].get(field) is None for field in FIELDS)
    state = pass_priority(state, seat)
    assert state.stack[-1].id == frame.id and state.priority_player == 3-seat
    state = pass_priority(state, 3-seat)
    assert not state.stack and state.cards[source.id].zone == Zone.GRAVEYARD
    assert state.players[seat].life == 20
    assert state.players[3-seat].life == (16 if 0 in pair else 20)
    assert state.cards['nonbasic'].zone == (Zone.GRAVEYARD if 2 in pair else Zone.BATTLEFIELD)
    for pid in (1, 2):
        assert state.cards[f'creature-{pid}'].counters.get('__damage_marked', 0) == (2 if 1 in pair else 0)
        assert all(state.cards[cid].zone == (Zone.GRAVEYARD if 3 in pair else Zone.HAND) for cid in hands[pid])
        assert len(state.players[pid].hand) == len(hands[pid])
    assert state.discards_this_turn == ({pid: len(hand) for pid, hand in hands.items()}
                                       if 3 in pair else {1: 0, 2: 0})
    assert state.cards[source.id].oracle_text == RAW['oracle_text']
    reload(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('wire', ['typed', 'raw'])
@pytest.mark.parametrize('field', FIELDS)
def test_internal_probe_packet_is_not_a_real_choose_two_cast_permission(seat, wire, field):
    state, source = position(seat)
    targets = {'mode_text': MODES[1], 'mode_texts': [],
               field: phantom_packet(seat, field, 'outer')[field]}
    before = pickle.dumps(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, action_for(source, targets, wire))
    assert pickle.dumps(state) == before
    assert not state.stack and state.cards[source.id].zone == Zone.HAND
    assert state.players[seat].mana_pool == {'R': 2, 'C': 3}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field', FIELDS)
def test_full_spell_admission_retains_outer_targetless_rejection_despite_branch_probes(seat, field):
    state, source = position(seat)
    before = pickle.dumps(state)
    spec = build_spell_spec(state, source, seat, phantom_packet(seat, field, 'outer'),
                            report_unsupported=False)
    assert spec.effect.key == 'noop' and spec.used_fallback
    assert 'unrecognized spell resolution' in spec.unsupported_resolution
    assert pickle.dumps(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field', FIELDS)
@pytest.mark.parametrize('wire', ['typed', 'raw'])
def test_existing_shared_and_per_mode_exclusivity_guard_remains_strict(seat, field, wire):
    state, source = position(seat)
    targets = phantom_packet(seat, field, 'outer')
    targets['mode_targets'] = announced(seat, (1, 3))['mode_targets']
    before = pickle.dumps(state)
    reason = ('Target stack item is unavailable' if field == 'target_stack_id'
              else 'Use either per-mode or shared targets, not both')
    with pytest.raises(ActionRejected, match=reason):
        checked_action(state, RulesEngine(), seat, action_for(source, targets, wire))
    assert pickle.dumps(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('wire', ['typed', 'raw'])
def test_paid_targetless_modes_survive_genuine_counter_response_without_phantom_targets(seat, wire, monkeypatch):
    state, source = position(seat)
    opposing_counter = add(state, 'Counterspell', 3-seat)
    own_counter = add(state, 'Counterspell', seat)
    state.players[seat].mana_pool.update({'U': 2})
    state.players[3-seat].mana_pool = {'U': 2}
    state = checked_action(state, RulesEngine(), seat, action_for(source, announced(seat, (1, 3)), wire))
    frame = deepcopy(state.stack[-1])
    assert frame.controller == seat and frame.source_card_id == source.id
    assert frame.targets == []
    assert frame.payload['__announced_target_references']['targets'] == {
        'mode_targets': {MODES[1]: {}, MODES[3]: {}}}
    assert frame.payload['mana_spent'] == 5
    assert state.players[seat].mana_pool.get('U') == 2
    state = pass_priority(state, seat)
    state = checked_action(state, RulesEngine(), 3-seat,
        {'type': 'cast_spell', 'card_id': opposing_counter.id, 'targets': {'target_stack_id': frame.id}})
    opposing_frame = deepcopy(state.stack[-1])
    assert opposing_frame.controller == 3-seat and opposing_frame.source_card_id == opposing_counter.id
    assert not any(state.players[3-seat].mana_pool.values())
    state = pass_priority(state, 3-seat)
    state = checked_action(state, RulesEngine(), seat,
        {'type': 'cast_spell', 'card_id': own_counter.id, 'targets': {'target_stack_id': opposing_frame.id}})
    assert state.stack[-1].source_card_id == own_counter.id and not any(state.players[seat].mana_pool.values())
    state = pass_priority(state, seat)
    state = pass_priority(state, 3-seat)
    assert len(state.stack) == 1 and state.stack[-1].id == frame.id
    assert state.cards[opposing_counter.id].zone == state.cards[own_counter.id].zone == Zone.GRAVEYARD
    assert state.stack[-1].payload == frame.payload
    hands = {pid: set(player.hand) for pid, player in state.players.items()}
    from effects import registry
    original = registry.resolve_effect
    observed = []

    def observe(current, controller, key, payload):
        observed.append(key)
        return original(current, controller, key, payload)

    monkeypatch.setattr(registry, 'resolve_effect', observe)
    state = pass_priority(state, state.priority_player)
    state = pass_priority(state, state.priority_player)
    assert observed[:2] == ['damage_each_creature', 'each_player_discard']
    assert not state.stack and state.cards[source.id].zone == Zone.GRAVEYARD
    for pid in (1, 2):
        assert state.cards[f'creature-{pid}'].counters['__damage_marked'] == 2
        assert all(state.cards[cid].zone == Zone.GRAVEYARD for cid in hands[pid])
        assert len(state.players[pid].hand) == len(hands[pid])
        assert state.players[pid].life == 20
    assert state.discards_this_turn == {pid: len(hand) for pid, hand in hands.items()}
    assert state.cards[source.id].oracle_text == RAW['oracle_text']
    reload(state)
