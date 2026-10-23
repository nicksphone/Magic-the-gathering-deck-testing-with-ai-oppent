"""Focused genuine admission witnesses. Authored only; parent owns native runs."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import unittest
from unittest.mock import patch

from card_data.sync import ScryfallSyncService
from game_state.state import CardInstance, MatchState, PlayerState, Zone
from tests import test_ai_recurring_engines as subject


FIXTURES = Path(__file__).parent / 'fixtures'
RAW_SHA = 'bbc868c335b6f5bc7e5a02f5aafe92bf16e25ede7652a0f2e7d5ae5428c5048a'
BEARS_SHA = '150049326ad0c3b914719c54709331b3a51d11a18c02dde60c64246f3ac8239c'
RIP_RAW_SHA = '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
RIP_PROVENANCE_SHA = '2c2750acb82ff6746cfbb4cb49c6118f276e9129fd2c819cbc2b5187e0b22f76'
FIELDS = ('name', 'mana_cost', 'type_line', 'types', 'power', 'toughness',
          'printed_power', 'printed_toughness', 'loyalty', 'oracle_text', 'keywords', 'colors')
PHYSICAL = (*FIELDS, 'card_faces', 'layout', 'selected_face_index', 'image_uri')


def independent_raw(name):
    if name == 'Blood Artist':
        encoded = (FIXTURES / 'pending_permanent_fullraw/canonical.jsonl').read_bytes()
        assert hashlib.sha256(encoded).hexdigest() == RAW_SHA
        rows = [json.loads(line) for line in encoded.splitlines()]
        raw = next(row for row in rows if row['name'] == name)
        assert raw['id'] == 'b5275d76-2947-4219-be21-614c7421614a'
    elif name == 'Rest in Peace':
        encoded = (FIXTURES / 'knowledge_profiles/seed155-scryfall.jsonl').read_bytes()
        assert hashlib.sha256(encoded).hexdigest() == RIP_RAW_SHA
        raw = json.loads(encoded.splitlines()[76])
        provenance = (FIXTURES / 'library_canonical_88/PROVENANCE.json').read_bytes()
        assert hashlib.sha256(provenance).hexdigest() == RIP_PROVENANCE_SHA
        record = json.loads(provenance)['objects'][name]
        assert record['source_line'] == 77 and record['file_sha256'] == RIP_RAW_SHA
        assert raw['id'] == record['id'] == 'd108c2b1-236e-4b8d-8445-d9749ccc4fea'
        assert raw['oracle_id'] == record['oracle_id'] == '087f9ad7-e74f-40e2-8102-1ed2925d0418'
        assert hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'),
            ensure_ascii=False).encode()).hexdigest() == record['object_sha256']
    else:
        assert name == 'Grizzly Bears'
        encoded = (FIXTURES / 'ai_terminal_draw/grizzly-bears.raw.json').read_bytes()
        assert hashlib.sha256(encoded).hexdigest() == BEARS_SHA
        raw = json.loads(encoded)
        assert raw['id'] == '409f9b88-f03e-40b6-9883-68c14c37c0de'
    assert raw['object'] == 'card' and raw['name'] == name
    assert len(raw) == (64 if name == 'Rest in Peace' else 66)
    return raw


def game():
    return MatchState(id='recurring-positive-fullraw', players={
        seat: PlayerState(id=seat, name=f'Seat {seat}') for seat in (1, 2)
    }, cards={}, stack=[], rng=random.Random(711))


def strict(actual, expected):
    assert type(actual) is type(expected)
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in expected:
            strict(actual[key], expected[key])
    elif isinstance(expected, (list, tuple)):
        assert len(actual) == len(expected)
        for left, right in zip(actual, expected):
            strict(left, right)
    else:
        assert actual == expected


class RecurringPositiveFullRaw(unittest.TestCase):
    def test_full_raw_precedes_normalization_and_genuine_birth(self):
        for name in ('Blood Artist', 'Grizzly Bears', 'Rest in Peace'):
            poses = ((1, Zone.BATTLEFIELD), (2, Zone.BATTLEFIELD), (1, Zone.HAND)) if name == 'Blood Artist' else (
                (1, Zone.BATTLEFIELD), (2, Zone.BATTLEFIELD))
            for seat, zone in poses:
                with self.subTest(name=name, seat=seat, zone=zone):
                    raw = independent_raw(name)
                    expected = {key: deepcopy(raw[key]) for key in (
                        'name', 'mana_cost', 'type_line', 'oracle_text', 'layout', 'colors', 'keywords')}
                    expected.update(types=['Enchantment'] if name == 'Rest in Peace' else ['Creature'],
                                    power=int(raw['power']) if raw.get('power') is not None else None,
                                    toughness=int(raw['toughness']) if raw.get('toughness') is not None else None,
                                    printed_power=raw.get('power'), printed_toughness=raw.get('toughness'),
                                    loyalty=None, card_faces=[], selected_face_index=None, image_uri=None)
                    state = game()
                    baseline = deepcopy(state)
                    expected_id = baseline.allocate_object_id()
                    root_rng = state.rng
                    rng, process_rng = root_rng.getstate(), random.getstate()
                    table = deepcopy(subject.CARDS)
                    events, inputs, births = [], [], []
                    native_normalize = ScryfallSyncService._normalize_payload
                    native_birth = CardInstance.__post_init__

                    def observe_normalize(cls, incoming, image_uri, rulings=None):
                        strict(incoming, raw)
                        assert image_uri, 'No placeholder/art writes'
                        events.append('normalize')
                        inputs.append(deepcopy(incoming))
                        return native_normalize.__func__(cls, incoming, image_uri, rulings)

                    def observe_birth(card):
                        events.append('birth')
                        assert card.id == expected_id and card.id not in state.cards
                        assert card.owner == card.controller == seat and card.zone == zone
                        assert card.summoning_sick is True and card.instance_order == 0
                        strict({key: deepcopy(getattr(card, key)) for key in PHYSICAL}, expected)
                        assert card.characteristic_record is None
                        births.append(card)
                        return native_birth(card)

                    with patch.object(ScryfallSyncService, '_normalize_payload', classmethod(observe_normalize)), \
                            patch.object(CardInstance, '__post_init__', observe_birth):
                        card = subject.add(state, name, seat, zone, full_printing=True)
                    assert events == ['normalize', 'birth'] and len(inputs) == len(births) == 1
                    assert births[0] is card and state.cards == {expected_id: card}
                    record = card.characteristic_record
                    assert type(record['version']) is int and record['version'] == 1
                    strict(record['physical'], expected)
                    strict(record['values'], {key: expected[key] for key in FIELDS})
                    getattr(baseline.players[seat], zone.value).append(expected_id)
                    strict({key: deepcopy(value) for key, value in vars(state).items() if key not in {'cards', 'rng'}},
                           {key: deepcopy(value) for key, value in vars(baseline).items() if key not in {'cards', 'rng'}})
                    assert state.rng is root_rng and state.rng.getstate() == rng and random.getstate() == process_rng
                    strict(subject.CARDS, table)
                    assert card.colors is not subject.CARDS[name]['colors']
                    assert card.keywords is not subject.CARDS[name]['keywords']
                    card.colors.append('U')
                    strict(subject.CARDS, table)
                    strict(inputs[0], raw)

    def test_default_helper_does_not_enter_full_raw_conversion(self):
        for name in ('Blood Artist', 'Grizzly Bears', 'Rest in Peace'):
            with self.subTest(name=name):
                state = game()
                with patch.object(ScryfallSyncService, '_normalize_payload',
                                  side_effect=AssertionError('default helper must not normalize')):
                    card = subject.add(state, name)
                assert card.name == name and card.zone == Zone.BATTLEFIELD
                assert card.characteristic_record['physical']['oracle_text'] == subject.CARDS[name]['oracle_text']

    def test_new_optin_rejects_unregistered_name_or_alternate_table_before_allocation(self):
        for name, table in (('Naturalize', subject.CARDS), ('Blood Artist', deepcopy(subject.CARDS))):
            with self.subTest(name=name, default_table=table is subject.CARDS):
                state = game()
                before = deepcopy(vars(state))
                with self.assertRaises(ValueError), patch.object(
                        ScryfallSyncService, '_normalize_payload', side_effect=AssertionError('must reject first')):
                    subject.add(state, name, cards=table, full_printing=True)
                assert state.rng.getstate() == before['rng'].getstate()
                assert {key: value for key, value in vars(state).items() if key != 'rng'} == {
                    key: value for key, value in before.items() if key != 'rng'}
