"""Public-only PRE evidence controls, independent of any protected receipt."""
from copy import deepcopy
import inspect
import random

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchState, PlayerState, StackItem, Step, Zone
from tests.natural_heat_diagnostic_support import canonical
from tests import test_natural_heat_target_audit as audit
from tests import test_natural_heat_scheduler_compat as scheduler


TARGET_REFERENCE = {'card_id': 'victim', 'incarnation': 11, 'zone_change_sequence': 4}
CAPTURE = {'status': 'captured', 'captured': True, 'target_refs': [TARGET_REFERENCE], 'receipts': []}
BINDING = {
    '__announced_stack_kind': 'spell',
    '__announced_target_references': {'version': 1, 'targets': {'target_card_id': TARGET_REFERENCE}},
    '__granted_target_capture': CAPTURE, '__granted_target_membership': [TARGET_REFERENCE],
    '__granted_target_published_capture': CAPTURE, '__granted_target_revision': 0,
}
LKI = {
    'reference': [11, 4], 'controller': 1, 'types': ['Creature'],
    'descriptor': {
        'name': 'Public Bear', 'mana_cost': '{1}{G}', 'type_line': 'Creature - Bear',
        'power': 2, 'toughness': 2, 'printed_power': '2', 'printed_toughness': '2',
        'oracle_text': '', 'keywords': [], 'colors': ['G'], 'image_uri': None, 'loyalty': None,
        'types': ['Creature', 'Token'],
    },
}


def public_pre():
    source = CardInstance('source', 'Shock', 1, 1, Zone.HAND, types=['Instant'],
                          mana_cost='{R}', oracle_text='Shock deals 2 damage to any target.',
                          colors=['R'], type_line='Instant')
    victim = CardInstance('victim', 'Public Bear', 1, 1, Zone.BATTLEFIELD, types=['Creature'],
                          mana_cost='{1}{G}', power=2, toughness=2, printed_power='2',
                          printed_toughness='2', colors=['G'], type_line='Creature - Bear',
                          battlefield_incarnation=11, zone_change_sequence=4)
    state = MatchState('public-pre', {1: PlayerState(1, 'One'), 2: PlayerState(2, 'Two')},
                       {'source': source, 'victim': victim}, [], rng=random.Random(731),
                       turn=5, step=Step.END_STEP, pregame_pending=False, kept_hands={1, 2},
                       spell_color_history_known=False, spells_cast_this_turn={1: 1, 2: 0})
    state.players[1].hand = ['source']
    state.players[1].battlefield = ['victim']
    state.players[1].mana_pool['R'] = 1
    raw = serialize_match_snapshot(state)
    raw.pop('spell_color_history')
    raw.pop('spell_color_history_known')
    row = {'pid': 1, 'action': {'type': 'cast_spell', 'card_id': 'source',
                               'targets': {'target_card_id': 'victim'}}, 'snapshot': raw}
    return row, deserialize_match_snapshot(raw)


def producer(name):
    helper = getattr(audit, name, None)
    assert callable(helper), 'Missing independent PRE evidence producer: ' + name
    return helper


def public_stack():
    row, state = public_pre()
    context = producer('_legacy_replay_context')(row, state)
    # This is an independent hand-declared stack, not a snapshot of replay output.
    state.players[1].hand = []
    state.cards['source'].zone = Zone.STACK
    state.stack = [StackItem('public-stack', 'source', 1, 'Shock', 'damage',
                            deepcopy(BINDING), ['victim'])]
    state.spell_color_history = {1: {'R'}, 2: set()}
    legacy_state = deepcopy(state)
    legacy_state.stack[0].payload = {}
    historical = serialize_match_snapshot(legacy_state)
    actual = serialize_match_snapshot(state)
    historical.pop('spell_color_history')
    historical.pop('spell_color_history_known')
    context['history'] = {'1': ['R'], '2': []}
    return actual, historical, context


def test_initial_context_has_five_independent_required_expectations():
    row, state = public_pre()
    before = canonical(row)
    context = producer('_legacy_replay_context')(row, state)
    assert context == {'history': {'1': [], '2': []}, 'history_known': False,
                       'source_id': 'source', 'binding': BINDING, 'departed_lki': {}}
    _ = serialize_match_snapshot(state)
    row['action']['card_id'] = 'corrupt'
    row['action']['targets']['target_card_id'] = 'corrupt'
    state.cards['victim'].battlefield_incarnation = 99
    state.cards['victim'].zone_change_sequence = 99
    assert context['source_id'] == 'source'
    assert context['binding'] == BINDING
    assert before != canonical(row)


def test_pre_capture_is_detached_from_mutable_actual_and_pre_state():
    row, state = public_pre()
    context = producer('_legacy_replay_context')(row, state)
    receipt = {'pid': 1, 'action': deepcopy(row['action'])}
    lki = producer('_capture_legacy_pre_step')(state, receipt, 'victim', context)
    assert context['history'] == {'1': ['R'], '2': []}
    assert lki == LKI
    context['departed_lki']['victim'] = lki
    expected_before = canonical(context)
    actual = serialize_match_snapshot(state)
    actual['cards']['victim']['colors'].append('R')
    actual['cards']['victim']['name'] = 'corrupt'
    actual['spell_color_history']['1'].append('B')
    state.cards['source'].colors[:] = ['B']
    state.cards['victim'].keywords.append('Flying')
    state.cards['victim'].battlefield_incarnation = 99
    assert canonical(context) == expected_before
    assert context['binding'] == BINDING
    assert context['departed_lki']['victim'] == LKI


@pytest.mark.parametrize('field', ['history', 'history_known', 'source_id', 'binding', 'departed_lki'])
def test_parity_requires_each_expected_input(field):
    actual, historical, context = public_stack()
    audit._assert_legacy_snapshot_parity(actual, historical, historical, **context)
    del context[field]
    with pytest.raises(TypeError):
        audit._assert_legacy_snapshot_parity(actual, historical, historical, **context)
    assert all(parameter.default is inspect.Parameter.empty for parameter in
               inspect.signature(audit._assert_legacy_snapshot_parity).parameters.values())


@pytest.mark.parametrize('corruption', ['history', 'known-type', 'version-type', 'captured-type',
                                      'revision-type', 'reference-type', 'raw-history'])
def test_public_parity_rejects_protocol_and_raw_omission_tamper(corruption):
    actual, historical, context = public_stack()
    original = deepcopy(historical)
    audit._assert_legacy_snapshot_parity(actual, historical, original, **context)
    expected_before = canonical(context)
    payload = actual['stack'][0]['payload']
    if corruption == 'history':
        actual['spell_color_history']['1'] = ['B']
    elif corruption == 'known-type':
        actual['spell_color_history_known'] = 0
    elif corruption == 'version-type':
        payload['__announced_target_references']['version'] = True
    elif corruption == 'captured-type':
        payload['__granted_target_capture']['captured'] = 1
    elif corruption == 'revision-type':
        payload['__granted_target_revision'] = False
    elif corruption == 'reference-type':
        payload['__announced_target_references']['targets']['target_card_id']['incarnation'] = 11.0
    else:
        original['spell_color_history_known'] = False
    actual_before, historical_before, original_before = map(canonical, (actual, historical, original))
    with pytest.raises(AssertionError):
        audit._assert_legacy_snapshot_parity(actual, historical, original, **context)
    assert canonical(context) == expected_before
    assert canonical(actual) == actual_before
    assert canonical(historical) == historical_before
    assert canonical(original) == original_before


@pytest.mark.parametrize('key,value', [('control_effect_base', 1), ('control_effects', [{'bad': True}]),
                                     ('kicker_count', 0), ('kicker_count', 'missing')])
def test_public_parity_rejects_nonempty_or_missing_observer_defaults(key, value):
    row, state = public_pre()
    context = producer('_legacy_replay_context')(row, state)
    # Independent public source-entry golden: no private receipt or replay output.
    state.players[1].hand = []
    state.players[1].graveyard = ['source']
    state.cards['source'].zone = Zone.GRAVEYARD
    card = serialize_match_snapshot(state)['cards']['source']
    card.update(control_effect_base=None, control_effects=[], kicker_count=None)
    state.card_observations = {1: {'source': deepcopy(card)}, 2: {'source': deepcopy(card)}}
    historical = serialize_match_snapshot(state)
    historical['card_observations'] = {'1': {}, '2': {}}
    actual = serialize_match_snapshot(state)
    historical.pop('spell_color_history')
    historical.pop('spell_color_history_known')
    expected = audit._legacy_snapshot_with_public_entry(historical, 'source')
    audit._assert_legacy_snapshot_parity(actual, expected, historical, **context)
    expected_before = canonical(context)
    if value == 'missing':
        actual['card_observations']['1']['source'].pop(key)
    else:
        actual['card_observations']['1']['source'][key] = value
    before = canonical(actual)
    with pytest.raises(AssertionError):
        audit._assert_legacy_snapshot_parity(actual, expected, historical, **context)
    assert canonical(actual) == before
    assert canonical(context) == expected_before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('queued_side', ['actual', 'expected'])
def test_scheduler_sibling_uses_independent_context_with_public_position(monkeypatch, seat, queued_side):
    monkeypatch.setattr(scheduler, 'exact_state', public_pre)
    scheduler.test_nondefault_canonical_queued_schedule_cannot_pass_legacy_parity(seat, queued_side)


def test_shared_replay_rejects_incorrect_historical_snapshot_after_real_action():
    row, state = public_pre()
    before = canonical(serialize_match_snapshot(state))
    replay = producer('_replay_legacy_receipts')
    # The immutable PRE snapshot is deliberately NOT a valid post-cast receipt.
    receipt = {'event': 'applied', 'tick': 303, 'pid': 1, 'action': deepcopy(row['action']),
               'snapshot': deepcopy(row['snapshot'])}
    with pytest.raises(AssertionError):
        replay(row, state, [receipt])
    assert canonical(serialize_match_snapshot(state)) == before


@pytest.mark.parametrize('corruption', ['descriptor', 'incarnation-type', 'sequence-type',
                                      'colors', 'loyalty', 'missing-observer-default'])
def test_public_death_lki_requires_exact_pre_evidence(corruption):
    row, pre_state = public_pre()
    context = producer('_legacy_replay_context')(row, pre_state)
    lki = producer('_capture_legacy_pre_step')(
        pre_state, {'pid': 2, 'action': {'type': 'pass_priority'}}, 'victim', context)
    assert lki == LKI
    context['departed_lki']['victim'] = lki
    # Independently declared old death reference and current committed reference.
    _, legacy = public_pre()
    legacy.players[1].battlefield = []
    legacy.players[1].graveyard = ['victim']
    legacy.cards['victim'].zone = Zone.GRAVEYARD
    raw_card = serialize_match_snapshot(legacy)['cards']['victim']
    legacy.card_observations = {1: {'victim': deepcopy(raw_card)}, 2: {'victim': deepcopy(raw_card)}}
    raw = serialize_match_snapshot(legacy)
    raw.pop('spell_color_history')
    raw.pop('spell_color_history_known')
    _, current = public_pre()
    current.players[1].battlefield = []
    current.players[1].graveyard = ['victim']
    current.cards['victim'].zone = Zone.GRAVEYARD
    current.cards['victim'].zone_change_sequence = 5
    current.cards['victim'].last_known_battlefield = {'loyalty': None, '__copiable_lki': deepcopy(LKI)}
    observed = serialize_match_snapshot(current)['cards']['victim']
    observed.update(control_effect_base=None, control_effects=[], kicker_count=None)
    current.card_observations = {1: {'victim': deepcopy(observed)}, 2: {'victim': deepcopy(observed)}}
    actual = serialize_match_snapshot(current)
    expected = audit._legacy_snapshot_with_committed_death(raw, 'victim', 4)
    audit._assert_legacy_snapshot_parity(actual, expected, raw, **context)
    context_before, raw_before = canonical(context), canonical(raw)
    actual_lki = actual['cards']['victim']['last_known_battlefield']['__copiable_lki']
    if corruption == 'descriptor':
        actual_lki['descriptor']['mana_cost'] = '{9}'
    elif corruption == 'incarnation-type':
        actual_lki['reference'][0] = 11.0
    elif corruption == 'sequence-type':
        actual_lki['reference'][1] = 4.0
    elif corruption == 'colors':
        actual_lki['descriptor']['colors'] = ['R']
    elif corruption == 'loyalty':
        actual['cards']['victim']['last_known_battlefield']['loyalty'] = 1
    else:
        actual['card_observations']['2']['victim'].pop('control_effect_base')
    actual_before, expected_before = canonical(actual), canonical(expected)
    with pytest.raises(AssertionError):
        audit._assert_legacy_snapshot_parity(actual, expected, raw, **context)
    assert canonical(context) == context_before
    assert canonical(raw) == raw_before
    assert canonical(actual) == actual_before
    assert canonical(expected) == expected_before
