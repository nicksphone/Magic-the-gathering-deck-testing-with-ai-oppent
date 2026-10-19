"""PUBLIC synthetic states and exact AST-isolated adapter code, never private17."""
import ast
from copy import deepcopy
import json
from pathlib import Path

import pytest

from card_data.sync import ScryfallSyncService
from game_state.observations import observe_cards
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Zone, object_incarnation
from rules_engine.events import capture_last_known_battlefield
from rules_engine.type_effects import effective_types
from rules_engine.zone_actions import put_into_graveyard
from tests.canonical_positive_fixtures import raw_card


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def adapter():
    path = Path(__file__).with_name('test_natural_heat_target_audit.py')
    tree = ast.parse(path.read_bytes(), filename=str(path))
    names = {'_current_legacy_snapshot', '_capture_legacy_pre_step', '_assert_legacy_snapshot_parity'}
    selected = [node for node in tree.body if (
        isinstance(node, ast.FunctionDef) and node.name in names
        or isinstance(node, ast.Assign) and any(isinstance(t, ast.Name)
            and t.id == 'DEFAULT_LEGACY_SCHEDULER' for t in node.targets))]
    assert len(selected) == 4
    assert not any(isinstance(n, ast.Name) and n.id in {'exact_state', 'receipts', 'witness'}
                   for node in selected for n in ast.walk(node))
    namespace = {'__name__': 'public_legacy_AST_code_protocol', 'deepcopy': deepcopy,
                 'serialize_match_snapshot': serialize_match_snapshot,
                 'deserialize_match_snapshot': deserialize_match_snapshot,
                 'Zone': Zone, 'effective_types': effective_types,
                 'object_incarnation': object_incarnation, 'canonical': canonical}
    # No module imports/top-level assignments/private fixtures are executed.
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


def public_position(seat, name, record_kind):
    deck = []
    for card_name in ('Grizzly Bears', 'Island', 'Teferi, Hero of Dominaria'):
        raw = raw_card(card_name)
        assert raw['object'] == 'card' and len(raw) > 30
        data = ScryfallSyncService._normalize_payload(raw, ScryfallSyncService._extract_remote_image_uri(raw))
        deck.append({**raw, **data, 'card_name': card_name, 'quantity': 8,
                     'colors': raw['colors'], 'card_faces': json.loads(data['card_faces_json'])})
    state = MatchFactory.from_decks(deck, deck, seed=217)
    card = next(c for c in state.cards.values() if c.owner == seat and c.name == name)
    getattr(state.players[seat], card.zone.value).remove(card.id)
    card.move_to_zone(Zone.BATTLEFIELD)
    state.players[seat].battlefield.append(card.id)
    if card.loyalty is not None:
        assert card.loyalty == 4
        card.loyalty = 2  # Deliberate live-counter pose, not a printed-value change.
    observe_cards(state, [card.id])
    snapshot = serialize_match_snapshot(state)
    if record_kind != 'valid':
        for row in [snapshot['cards'][card.id], *[
                snapshot['card_observations'][s][card.id] for s in ('1', '2')]]:
            if record_kind == 'missing':
                del row['characteristic_record']
            else:
                row['characteristic_record'] = None if record_kind == 'null' else {}
        state = deserialize_match_snapshot(snapshot)
        card = state.cards[card.id]
        assert type(card.characteristic_record) is dict and card.characteristic_record == {}
    source = next(c for c in state.cards.values() if c.owner == seat and c.name == 'Island' and c.id != card.id)
    current = serialize_match_snapshot(state)
    context = {'history': deepcopy(current['spell_color_history']),
               'history_known': current['spell_color_history_known'], 'source_id': source.id,
               'binding': {}, 'departed_lki': {}}
    return state, card, context


def pre_capture(state, card, context):
    before = canonical(serialize_match_snapshot(state))
    result = adapter()['_capture_legacy_pre_step'](
        state, {'pid': card.controller, 'action': {'type': 'pass_priority'}}, card.id, context)
    assert canonical(serialize_match_snapshot(state)) == before
    return result


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Grizzly Bears', 'Island', 'Teferi, Hero of Dominaria'])
@pytest.mark.parametrize('record_kind', ['missing', 'null', 'empty', 'valid'])
def test_exact_capture_body_matches_independent_PRE_availability_and_values(seat, name, record_kind):
    state, card, context = public_position(seat, name, record_kind)
    record, live = deepcopy(card.characteristic_record), card.loyalty
    captured = pre_capture(state, card, context)
    expected = {'reference': [object_incarnation(card), card.zone_change_sequence],
                'controller': seat, 'types': list(card.types)}
    if record_kind == 'valid':
        descriptor = deepcopy(record['values'])
        descriptor.update(types=list(dict.fromkeys([*descriptor['types'], 'Token'])),
                          colors=descriptor['colors'] or [], image_uri=card.image_uri)
        expected['descriptor'] = descriptor
    else:
        expected.update(descriptor=None, unavailable='missing_copiable_characteristics')
    capture_last_known_battlefield(state, card.id)
    # Accept the old return ABI only to expose the real value/availability mismatch.
    actual_copy = captured.get('__copiable_lki', captured)
    assert canonical(actual_copy) == canonical(expected)
    assert canonical(card.last_known_battlefield['__copiable_lki']) == canonical(expected)
    assert card.last_known_battlefield['loyalty'] == live
    if record_kind == 'valid' and name.startswith('Teferi'):
        assert expected['descriptor']['loyalty'] == 4 and live == 2
    assert card.characteristic_record == record


def parity_case(seat, record_kind, name='Teferi, Hero of Dominaria'):
    state, card, context = public_position(seat, name, record_kind)
    context['departed_lki'][card.id] = pre_capture(state, card, context)
    capture_last_known_battlefield(state, card.id)
    state.players[seat].battlefield.remove(card.id)
    assert put_into_graveyard(state, card.id) == Zone.GRAVEYARD
    assert card.id in state.players[seat].graveyard
    actual = serialize_match_snapshot(state)
    historical = deepcopy(actual)
    for row in [historical['cards'][card.id], *[
            historical['card_observations'][s][card.id] for s in ('1', '2')]]:
        row['last_known_battlefield'].pop('loyalty')
        row['last_known_battlefield'].pop('__copiable_lki')
    for s in ('1', '2'):
        historical['card_observations'][s][card.id].pop('characteristic_record')
    return state, card, context, actual, historical


def check_parity(actual, historical, context):
    originals = canonical((actual, historical, context))
    adapter()['_assert_legacy_snapshot_parity'](actual, historical, historical, **context)
    assert canonical((actual, historical, context)) == originals


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('record_kind', ['missing', 'valid'])
def test_exact_parity_validates_new_fields_before_historical_projection(seat, record_kind):
    _state, _card, context, actual, historical = parity_case(seat, record_kind)
    check_parity(actual, historical, context)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('record_kind', ['missing', 'valid'])
@pytest.mark.parametrize('corruption', [
    'reference-type', 'copy-controller', 'copy-types', 'descriptor', 'availability-tag',
    'live-loyalty', 'observed-record', 'observed-name', 'sequence', 'life',
    'hidden-card', 'missing-observation',
])
def test_public_protocol_preserves_strict_privacy_mutation_and_reference_guards(seat, record_kind, corruption):
    state, card, context, actual, historical = parity_case(seat, record_kind)
    check_parity(actual, historical, context)
    bad = deepcopy(actual)
    copy = bad['cards'][card.id]['last_known_battlefield']['__copiable_lki']
    if corruption == 'reference-type':
        copy['reference'][0] = float(copy['reference'][0])
    elif corruption == 'copy-controller':
        copy['controller'] = 3 - seat
    elif corruption == 'copy-types':
        copy['types'] = ['UnrelatedProtocolType']
    elif corruption == 'descriptor':
        copy['descriptor'] = {} if copy['descriptor'] is None else {**copy['descriptor'], 'mana_cost': 'incorrect'}
    elif corruption == 'availability-tag':
        copy['unavailable'] = 'incorrect'
    elif corruption == 'live-loyalty':
        bad['cards'][card.id]['last_known_battlefield']['loyalty'] = 99
    elif corruption == 'observed-record':
        bad['card_observations'][str(seat)][card.id]['characteristic_record'] = {'forged': True}
    elif corruption == 'observed-name':
        bad['card_observations'][str(seat)][card.id]['name'] = 'corrupt public identity'
    elif corruption == 'sequence':
        bad['cards'][card.id]['zone_change_sequence'] += 1
    elif corruption == 'life':
        bad['players'][str(seat)]['life'] += 1
    elif corruption == 'hidden-card':
        cid = state.players[3-seat].library[0]
        bad['card_observations'][str(seat)][cid] = deepcopy(bad['cards'][cid])
    else:
        del bad['card_observations'][str(seat)][card.id]
    before = canonical((bad, historical, context))
    with pytest.raises((AssertionError, KeyError)):
        adapter()['_assert_legacy_snapshot_parity'](bad, historical, historical, **context)
    assert canonical((bad, historical, context)) == before


@pytest.mark.parametrize('corruption', ['bool-version', 'physical-key', 'values-float', 'values-extra'])
def test_PRE_oracle_refuses_malformed_populated_records_instead_of_reconstructing(corruption):
    state, card, context = public_position(1, 'Grizzly Bears', 'valid')
    if corruption == 'bool-version':
        card.characteristic_record['version'] = True
    elif corruption == 'physical-key':
        del card.characteristic_record['physical']['name']
    elif corruption == 'values-float':
        card.characteristic_record['values']['power'] = 2.0
    else:
        card.characteristic_record['values']['unknown'] = True
    before = canonical(serialize_match_snapshot(state))
    with pytest.raises(AssertionError):
        pre_capture(state, card, context)
    assert canonical(serialize_match_snapshot(state)) == before
