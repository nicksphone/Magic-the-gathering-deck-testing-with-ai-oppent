"""Retained HAND protocol boundaries and actual paid copies; no SQL/network."""
from copy import deepcopy
import hashlib
import json

import pytest

from ai.information import decision_view
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import ActionRejected
from rules_engine.damage_results import validate_hand_payload, damage_source_control, source_has_keyword
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.targeting import stack_source_card, stack_object_kind
from rules_engine.protection import source_matches_quality
from rules_engine.replacement import replacement_options
from effects.registry import resolve_effect
from tests import test_hand_source_incarnation_causal_audit as original
from tests.queued_sequence_support import FIXTURE, RAW
from tests.test_kozilek_graveyard_trigger_audit import FRESH
from tests.test_linked_damage_targets import raw_card
from tests import test_soulscar_protection_boundaries as protection

proof = json.loads((FIXTURE / 'provenance.json').read_text())
assert hashlib.sha256((FIXTURE / 'canonical.json').read_bytes()).hexdigest() == proof['canonical_sha256']
assert hashlib.sha256(json.dumps(RAW['Lithoform Engine'], sort_keys=True, separators=(',', ':')).encode()).hexdigest() == proof['rows']['Lithoform Engine']['raw_sha256']


def announced(seat=1, family='sniper'):
    state, source, target, spells = original.setup(seat, family, suppress_entry=False)
    state, frame, reference = original.announce(state, source, target, seat)
    return state, source, target, spells, frame, reference


def snapshot(state):
    return serialize_match_snapshot(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['sniper', 'land'])
def test_real_precost_hand_context_root_query_and_snapshot(seat, family):
    state, source, target, _, frame, ref = announced(seat, family)
    item = next(item for item in state.stack if item.id == frame)
    context = item.payload['__activation_source_context']
    assert context['controller'] is None and context['owner'] == seat
    assert context['source_reference'] == ref and context['origin_zone'] == 'hand'
    assert context['ability']['text'] == item.payload['__ability_target_text']
    before = snapshot(state)
    assert damage_source_control(state, source, source_context=context) is None
    view = stack_source_card(state, item)
    assert view is not state.cards[source]
    assert source_matches_quality(view, 'red' if family == 'sniper' else 'colorless', state=state)
    assert stack_object_kind(state, item) == 'activated'
    assert not source_has_keyword(state, source, 'lifelink', source_context=context)
    options = replacement_options(state, 'damage_to_permanent', target_card_id=target,
        source_card_id=source, amount=2, source_context=context, combat=False)
    assert not options
    assert snapshot(state) == before
    original.reload_exact(state)
    for actor in (1, 2):
        public, _ = decision_view(state, actor, original.RULES.legal_moves(state, actor))
        assert public.ai_information_player == actor


BAD = ['context-null', 'context-list', 'version-bool', 'extra', 'owner-bool', 'controller',
       'reference-bool', 'reference-list', 'reference-negative', 'source-id', 'types-empty',
       'types-unknown', 'colors-duplicate', 'colors-unknown', 'keywords-null', 'keywords-bool',
       'ability-null', 'index-bool', 'text-mismatch', 'cost-unsupported', 'origin-missing',
       'origin-foreign', 'lki-conflict', 'ref-missing', 'body-missing', 'infect', 'wither',
       'unknown-origin', 'missing-context']


def corrupt(payload, case):
    context = payload['__activation_source_context']
    if case == 'context-null': payload['__activation_source_context'] = None
    elif case == 'context-list': payload['__activation_source_context'] = []
    elif case == 'version-bool': context['version'] = True
    elif case == 'extra': context['new'] = 0
    elif case == 'owner-bool': context['owner'] = True
    elif case == 'controller': context['controller'] = 1
    elif case == 'reference-bool': context['source_reference']['incarnation'] = False
    elif case == 'reference-list': context['source_reference'] = []
    elif case == 'reference-negative': context['source_reference']['incarnation'] = -1
    elif case == 'source-id': context['source_card_id'] = 'foreign'
    elif case == 'types-empty': context['types'] = []
    elif case == 'types-unknown': context['types'] = ['Bogus']
    elif case == 'colors-duplicate': context['colors'] = ['R', 'R']
    elif case == 'colors-unknown': context['colors'] = ['Z']
    elif case == 'keywords-null': context['keyword_counts'] = None
    elif case == 'keywords-bool': context['keyword_counts']['lifelink'] = True
    elif case == 'ability-null': context['ability'] = None
    elif case == 'index-bool': context['ability']['index'] = True
    elif case == 'text-mismatch': context['ability']['text'] += ' draw a card.'
    elif case == 'cost-unsupported': context['ability']['cost'] += ', unknown cost'
    elif case == 'origin-missing': del payload['__activation_source_origin']
    elif case == 'origin-foreign': payload['__activation_source_origin'] = 'battlefield'
    elif case == 'lki-conflict': payload['__source_lki'] = {'controller': 1}
    elif case == 'ref-missing': del payload['__activation_source_reference']
    elif case == 'body-missing': del payload['__ability_target_text']
    elif case in ('infect', 'wither'): context['keyword_counts'][case] = 1
    elif case == 'unknown-origin': payload['__activation_source_origin'] = 'bogus'
    elif case == 'missing-context': del payload['__activation_source_context']
    else: raise AssertionError(case)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', BAD)
def test_protocol_corruption_rejects_before_direct_pop_fullroot(seat, case):
    state, _, _, _, frame, _ = announced(seat)
    item = next(item for item in state.stack if item.id == frame)
    corrupt(item.payload, case)
    before = snapshot(state)
    with pytest.raises(ActionRejected):
        resolve_top_of_stack(state)
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['context', 'source', 'ref', 'body', 'lki', 'effects-list'])
def test_protocol_sequence_child_corruption_precedes_first_damage(seat, case):
    state, source, _, _, frame, _ = announced(seat)
    item = next(item for item in state.stack if item.id == frame)
    root = {**deepcopy(item.payload), '__source_card_id': source}
    later = {'target_player': 3-seat, 'amount': 1}
    if case == 'context': later['__activation_source_context'] = None
    elif case == 'source': later['__source_card_id'] = 'foreign'
    elif case == 'ref': later['__activation_source_reference'] = {'incarnation': 9, 'zone_change_sequence': 9}
    elif case == 'body': later['__ability_target_text'] = 'different body'
    elif case == 'lki': later['__source_lki'] = {'controller': seat}
    root['effects'] = [
        {'effect_key': 'deal_damage', 'payload': {'target_player': 3-seat, 'amount': 1}},
        {'effect_key': 'deal_damage', 'payload': later}]
    if case == 'effects-list': root['effects'] = None
    before = snapshot(state)
    with pytest.raises(ActionRejected): resolve_effect(state, seat, 'effect_sequence', root)
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('copier_opposes', [False, True])
@pytest.mark.parametrize('family,retarget', [('sniper', False), ('sniper', True), ('land', False)])
def test_actual_paid_lithoform_hand_copy_retains_original_source_not_copy_controller(seat, copier_opposes, retarget, family):
    state, source, target, spells, original_frame, ref = announced(seat, family)
    copier_seat = 3-seat if copier_opposes else seat
    copier = raw_card(state, RAW['Lithoform Engine'], copier_seat, Zone.BATTLEFIELD)
    before = deepcopy(next(item.payload['__activation_source_context'] for item in state.stack if item.id == original_frame))
    state = original.priority(state, copier_seat)
    pool = deepcopy(state.players[copier_seat].mana_pool)
    if copier_opposes:
        old = snapshot(state)
        with pytest.raises(ActionRejected):
            original.act(state, copier_seat, {'type': 'activate_ability', 'card_id': copier.id,
                'ability_index': 0, 'targets': {'target_stack_id': original_frame}})
        assert snapshot(state) == old
        return  # Canonical Lithoform can only copy an ability its controller controls.
    state = original.act(state, copier_seat, {'type': 'activate_ability', 'card_id': copier.id,
        'ability_index': 0, 'targets': {'target_stack_id': original_frame}})
    assert state.cards[copier.id].tapped and state.players[copier_seat].mana_pool != pool
    state = original.until(state, lambda s: any(item.payload.get('__copied_from_stack_id') == original_frame for item in s.stack))
    pending = state.pending_mechanic_choice
    if family == 'sniper':
        assert pending['kind'] == 'copy_target'
        choice = 'target_player:' + str(seat) if retarget else 'keep'
        assert choice in pending['options']
        state = original.act(original.reload_exact(state), copier_seat, {'type': 'choose_mechanic', 'card_ids': [choice]})
    else:
        assert pending is None  # Only the original attacking creature is a legal recipient.
    copied = next(item for item in state.stack if item.payload.get('__copied_from_stack_id') == original_frame)
    assert copied.id != original_frame and copied.controller == copier_seat
    assert copied.payload['__activation_source_context'] == before
    assert copied.payload['__activation_source_reference'] == ref
    assert stack_object_kind(state, copied) == 'activated'
    copy_id = copied.id
    if family == 'land':
        state = original.reenter(state, seat, family, source, copy_id, spells)
        state = original.depart(state, seat, family, source, copy_id, spells)
        assert next(item for item in state.stack if item.id == copy_id).payload['__activation_source_context'] == before
    # Real Stifle removes the original ability, not the independent copy.
    stifle = raw_card(state, FRESH['Stifle'], 3-seat, Zone.HAND)
    state, response = original.cast(state, stifle.id, 3-seat, {'target_stack_id': original_frame})
    state = original.resolve_response(state, response, copy_id)
    assert not any(item.id == original_frame for item in state.stack)
    state = original.until(original.reload_exact(state), lambda s: not any(item.id == copy_id for item in s.stack))
    if family == 'sniper':
        damaged = seat if retarget else 3-seat
        assert state.players[damaged].life == 18
        assert state.players[3-damaged].life == 20
    else:
        assert state.cards[target].counters.get('__damage_marked') == 4


@pytest.mark.parametrize('seat', [1, 2])
def test_protocol_existing_hand_frame_stays_ability_when_physical_source_is_stack_spell(seat):
    state, source, _, _, frame, _ = announced(seat)
    item = next(item for item in state.stack if item.id == frame)
    # Explicit protocol seam, not a lawful recast episode or copy certificate.
    state.cards[source].zone = Zone.STACK
    before = snapshot(state)
    assert stack_object_kind(state, item) == 'activated'
    assert snapshot(state) == before


def shield_pause(seat, chain=True):
    state, source, target, spells, original_frame, ref = announced(seat)
    if chain:
        raw_card(state, protection.base.CARDS['Furnace of Rath'], seat, Zone.BATTLEFIELD)
    for _ in range(2):
        salve = raw_card(state, protection.base.CARDS['Healing Salve'], 3-seat, Zone.HAND)
        from rules_engine.oracle_effects import inspect_target_hints
        mode = next(mode for mode in inspect_target_hints(state, state.cards[salve.id], 3-seat)['modes']
                    if mode.startswith('Prevent'))
        state, response = original.cast(state, salve.id, 3-seat, {'mode_text': mode, 'target_player': 3-seat})
        state = original.resolve_response(state, response, original_frame)
    assert len(state.numeric_prevention_shields) == 2
    state.replacement_choice_required = True
    state.replacement_choice_players = {1, 2}
    state = original.until(state, lambda s: s.pending_replacement_choice is not None)
    assert state.pending_replacement_choice['stack_id'] == original_frame
    if chain:
        double = next(option['source_id'] for option in state.pending_replacement_choice['options']
                      if option['name'] == 'Furnace of Rath')
        state = original.act(state, 3-seat, {'type': 'choose_replacement', 'replacement_source_id': double})
        assert state.pending_replacement_choice['resume_kind'] == 'damage_chain'
        assert state.pending_replacement_choice['amount'] == 4
    return state, source


@pytest.mark.parametrize('seat', [1, 2])
def test_real_numeric_shield_hand_damage_partial_pause_restart_and_single_event(seat):
    state, source = shield_pause(seat)
    context = deepcopy(state.pending_replacement_choice['source_payload']['__activation_source_context'])
    frame = state.pending_replacement_choice['resolving_item']
    assert frame['payload']['__activation_source_context'] == context
    for expected_amount in (4, 1):
        state = original.reload_exact(state)
        assert state.pending_replacement_choice['amount'] == expected_amount
        choice = next(option['source_id'] for option in state.pending_replacement_choice['options']
                      if option['source_id'].startswith('numeric-prevention:'))
        state = original.act(state, 3-seat, {'type': 'choose_replacement', 'replacement_source_id': choice})
    assert state.pending_replacement_choice is None and not state.stack
    assert state.players[1].life == state.players[2].life == 20
    assert sorted(receipt.remaining for receipt in state.numeric_prevention_shields) == [0, 2]
    original.reload_exact(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('phase', ['stack', 'chain'])
@pytest.mark.parametrize('case', ['missing', 'context', 'ref', 'foreign', 'remaining'])
def test_protocol_paused_damage_corruption_rejects_before_clear_log_fullroot(seat, phase, case):
    state, source = shield_pause(seat, chain=phase == 'chain')
    pending = state.pending_replacement_choice
    if phase == 'chain':
        data = pending['source_payload']
    else:
        data = state.stack[-1].payload
    if case == 'missing': del data['__activation_source_context']
    elif case == 'context': data['__activation_source_context'] = None
    elif case == 'ref': data['__activation_source_reference'] = {'incarnation': 999, 'zone_change_sequence': 999}
    elif case == 'foreign': data['__activation_source_context']['source_card_id'] = 'foreign'
    elif case == 'remaining':
        if phase == 'stack': data['effects'] = [{'effect_key': 'deal_damage', 'payload': {'__activation_source_context': None}}]
        else: pending['continuation_effects'] = [{'effect_key': 'deal_damage', 'payload': {'__activation_source_context': None}}]
    before = snapshot(state)
    choice = pending['options'][0]['source_id']
    with pytest.raises(ActionRejected):
        original.RULES.take_action(state, 3-seat, {'type': 'choose_replacement', 'replacement_source_id': choice}, reject_invalid=True)
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['context-bool', 'reference-bool', 'context-list', 'context-keywords-null'])
def test_protocol_equal_python_bool_is_not_equal_typed_child_context(seat, case):
    state, source, _, _, frame, _ = announced(seat)
    root = {**deepcopy(next(item.payload for item in state.stack if item.id == frame)), '__source_card_id': source}
    child = {**deepcopy(root), 'target_player': 3-seat, 'amount': 1}
    if case == 'context-bool': child['__activation_source_context']['version'] = True
    elif case == 'reference-bool': child['__activation_source_reference']['incarnation'] = False
    elif case == 'context-list': child['__activation_source_context'] = ['not-context']
    else: child['__activation_source_context']['keyword_counts'] = None
    root['effects'] = [{'effect_key': 'deal_damage', 'payload': {'amount': 1, 'target_player': 3-seat}},
                       {'effect_key': 'deal_damage', 'payload': child}]
    before = snapshot(state)
    with pytest.raises(ActionRejected): resolve_effect(state, seat, 'effect_sequence', root)
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['missing-origin-context', 'absent-instance', 'spell-copy-conflict', 'trigger-conflict'])
def test_protocol_old_hand_native_cannot_be_repaired_from_current_card(seat, case):
    state, source, _, _, frame, _ = announced(seat)
    payload = next(item.payload for item in state.stack if item.id == frame)
    if case == 'missing-origin-context':
        del payload['__activation_source_context']
        del payload['__activation_source_origin']
    elif case == 'absent-instance': del state.cards[source]
    elif case == 'spell-copy-conflict': payload['__stack_copy_kind'] = 'spell'
    else: payload['__trigger_event'] = 'enters_battlefield'
    before = snapshot(state)
    with pytest.raises(ActionRejected): resolve_top_of_stack(state)
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_protocol_retained_hand_sequence_complete_damage_no_later_whip_lifelink(seat):
    state, source, _, _, frame, _ = announced(seat)
    payload = {**deepcopy(next(item.payload for item in state.stack if item.id == frame)), '__source_card_id': source}
    payload['effects'] = [{'effect_key': 'deal_damage', 'payload': {'target_player': 3-seat, 'amount': 1}},
                          {'effect_key': 'deal_damage', 'payload': {'target_player': 3-seat, 'amount': 1}}]
    resolve_effect(state, seat, 'effect_sequence', payload)
    assert state.players[seat].life == 20 and state.players[3-seat].life == 18
    assert source_has_keyword(state, source, 'reach', source_context=payload['__activation_source_context'])


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['context', 'ref-bool', 'source', 'lki', 'recipients-shape'])
def test_protocol_entire_hand_batch_preflight_before_first_recipient(seat, case):
    state, source, _, _, frame, _ = announced(seat)
    payload = {**deepcopy(next(item.payload for item in state.stack if item.id == frame)), '__source_card_id': source}
    later = {'target_player': seat, 'amount': 1}
    if case == 'context': later['__activation_source_context'] = None
    elif case == 'ref-bool': later['__activation_source_reference'] = {'incarnation': False, 'zone_change_sequence': 1}
    elif case == 'source': later['__source_card_id'] = 'foreign'
    elif case == 'lki': later['__source_lki'] = {'controller': seat}
    payload['recipients'] = [{'target_player': 3-seat, 'amount': 1}, later]
    if case == 'recipients-shape': payload['recipients'] = [None]
    before = snapshot(state)
    with pytest.raises(ActionRejected): resolve_effect(state, seat, 'deal_damage_batch', payload)
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family,amount', [('sniper', 2), ('land', 4)])
def test_actual_paid_hand_source_is_not_controlled_for_either_real_mage(seat, family, amount):
    state, source, target, _ = original.setup(seat, family, suppress_entry=False)
    mages = [raw_card(state, protection.base.CARDS['Soul-Scar Mage'], actor, Zone.BATTLEFIELD).id
             for actor in (1, 2)]
    state = original.priority(state, seat)
    from rules_engine.oracle_effects import extract_activated_abilities
    ability = next(ability for ability in extract_activated_abilities(state.cards[source])
                   if ability['activation_zone'] == 'hand')
    state = original.act(state, seat, {'type': 'activate_ability', 'card_id': source,
        'ability_index': ability['index'], 'targets': {'target_card_id': target}})
    frame = next(item for item in state.stack if item.source_card_id == source)
    before = snapshot(state)
    options = replacement_options(state, 'damage_to_permanent', target_card_id=target,
        source_card_id=source, amount=amount, source_context=frame.payload['__activation_source_context'])
    assert not any(option['source_id'] in mages for option in options)
    assert snapshot(state) == before
    state = original.until(original.reload_exact(state), lambda s: not any(item.id == frame.id for item in s.stack))
    assert state.cards[target].counters.get('__damage_marked') == amount
    assert not state.cards[target].counters.get('-1/-1')
    assert state.players[1].life == state.players[2].life == 20
