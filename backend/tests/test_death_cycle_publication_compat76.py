"""Genuine cycling receipts plus deliberately corrupted observer-protocol controls."""
from copy import deepcopy
from dataclasses import asdict

import pytest

from game_state.serializers import serialize_match_snapshot
from tests import test_death_cycle_committed_publication as publication


def captured(monkeypatch, seat, name='Shark Typhoon', mode='none'):
    state, source, action = publication.audit.cycle_position(seat, name, mode)
    before = serialize_match_snapshot(state)
    paid, records = publication.capture_action(state, seat, action, monkeypatch)
    assert serialize_match_snapshot(state) == before
    aliases = [
        ('discard', [{'card_id': source.id, 'controller': seat}]),
        ('cycle', [{'card_id': source.id, 'controller': seat,
                    'x_value': action.get('x_value', 0)}]),
    ]
    return source, paid, records, aliases


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mode', ['none', 'rip'])
@pytest.mark.parametrize('name', ['Shark Typhoon', 'Krosan Tusker'])
def test_complete_actual_activation_is_bound_to_real_paid_item_and_order(monkeypatch, seat, mode, name):
    source, paid, records, aliases = captured(monkeypatch, seat, name, mode)
    destination = publication.audit.destination(mode, seat, source.owner)
    publication.assert_hand_entry(records, source, seat, destination, aliases)
    rows = [row for row in records if row['event'] == 'nonmana_ability_activated']
    assert len(rows) == 1
    original, = [item for item in paid.stack
                 if item.source_card_id == source.id and item.effect_key == 'cycle_draw']
    assert rows[0]['payloads'] == [{'controller': seat, 'source_stack_id': original.id,
                                   'original_item': asdict(original)}]
    assert rows[0]['stack_at_event'] == rows[0]['state_at_event']['stack']
    assert rows[0]['payloads'][0]['original_item']['payload']['__completed_nonmana_activation'] is True
    assert [row['event'] for row in records] == (
        (['enters_graveyard'] if destination == publication.Zone.GRAVEYARD else [])
        + ['nonmana_ability_activated', 'discard', 'cycle'])


CORRUPTIONS = [
    'drop-activation', 'duplicate-activation', 'late-activation',
    'unexpected-event', 'empty-batch', 'event-controller', 'event-stack-id',
    'retained-source', 'retained-controller', 'retained-label', 'retained-effect',
    'retained-payload', 'retained-payload-field-loss', 'retained-targets',
    'frame-source', 'frame-kind-and-receipt', 'frame-incomplete-and-receipt',
    'frame-copy-and-receipt', 'snapshot-stack', 'graveyard-receipt',
    'discard-alias', 'cycle-alias',
]


def corrupt(records, source, seat, kind):
    """Mutate only cloned test-protocol receipts, never a game card or Oracle row."""
    rows = deepcopy(records)
    activation = next(row for row in rows if row['event'] == 'nonmana_ability_activated')
    payload = activation['payloads'][0]
    retained = payload['original_item']
    frame = next(item for item in activation['stack_at_event'] if item['source_card_id'] == source.id)
    snapshot = next(item for item in activation['state_at_event']['stack'] if item['source_card_id'] == source.id)
    if kind == 'drop-activation':
        rows.remove(activation)
    elif kind == 'duplicate-activation':
        rows.insert(rows.index(activation), deepcopy(activation))
    elif kind == 'late-activation':
        rows.remove(activation)
        rows.append(activation)
    elif kind in ('unexpected-event', 'empty-batch'):
        extra = deepcopy(activation)
        extra['event'] = 'deliberate-observer-protocol-negative'
        if kind == 'empty-batch':
            extra['payloads'] = []
        rows.insert(0, extra)
    elif kind == 'event-controller':
        payload['controller'] = 3 - seat
    elif kind == 'event-stack-id':
        payload['source_stack_id'] = 'unrelated-protocol-id'
    elif kind == 'retained-source':
        retained['source_card_id'] = 'unrelated-protocol-source'
    elif kind == 'retained-controller':
        retained['controller'] = 3 - seat
    elif kind == 'retained-label':
        retained['label'] = 'incorrect-protocol-label'
    elif kind == 'retained-effect':
        retained['effect_key'] = 'cycle_search'
    elif kind == 'retained-payload':
        retained['payload']['amount'] = 2
    elif kind == 'retained-payload-field-loss':
        del retained['payload']['__granted_target_capture']
    elif kind == 'retained-targets':
        retained['targets'] = ['unrelated-protocol-target']
    elif kind == 'frame-source':
        frame['source_card_id'] = 'unrelated-protocol-source'
    elif kind in ('frame-kind-and-receipt', 'frame-incomplete-and-receipt', 'frame-copy-and-receipt'):
        key, value = {
            'frame-kind-and-receipt': ('__announced_stack_kind', 'spell'),
            'frame-incomplete-and-receipt': ('__completed_nonmana_activation', False),
            'frame-copy-and-receipt': ('__stack_copy_kind', 'ability'),
        }[kind]
        for item in (frame, retained, snapshot):
            item['payload'][key] = value
    elif kind == 'snapshot-stack':
        activation['state_at_event']['stack'] = []
    elif kind == 'graveyard-receipt':
        rows[0]['payloads'][0]['entry_reference']['zone_change_sequence'] = 2
    elif kind == 'discard-alias':
        next(row for row in rows if row['event'] == 'discard')['payloads'][0]['controller'] = 3 - seat
    elif kind == 'cycle-alias':
        next(row for row in rows if row['event'] == 'cycle')['payloads'][0]['x_value'] = 99
    else:
        raise AssertionError('Undeclared protocol corruption')
    return rows


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', CORRUPTIONS)
def test_complete_observer_rejects_corrupt_or_missing_publication(monkeypatch, seat, kind):
    source, _paid, records, aliases = captured(monkeypatch, seat)
    before = deepcopy(records)
    invalid = corrupt(records, source, seat, kind)
    with pytest.raises(AssertionError):
        publication.assert_hand_entry(invalid, source, seat, publication.Zone.GRAVEYARD, aliases)
    assert records == before
