"""Full printed inputs observed before the original allocation consumers."""
from copy import deepcopy
from dataclasses import fields
import hashlib
import json
from pathlib import Path

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.engine import RulesEngine
from tests import test_ai_allocation_contracts as original
from tests.library_canonical_fixtures import PRINTED


ROOT = Path(__file__).parent / 'fixtures'
SOURCES_SHA = '016f2483ed3eca00d259914b81bfa8668a636bf56d0c3d1fa355dd950d1e9b4d'
CASES = [
    ('Phantom Nishoba', original.test_ai_uses_the_fixed_damage_budget_and_an_enemy_recipient),
    ('Grizzly Bears', original.test_ai_uses_the_fixed_damage_budget_and_an_enemy_recipient),
    ('Pyrotechnics', original.test_ai_uses_the_fixed_damage_budget_and_an_enemy_recipient),
    ('Prodigal Pyromancer', original.test_generic_targeted_activation_gets_a_materialized_enemy_target),
]


class Consumed(BaseException):
    pass


def raw_card(name):
    data = (ROOT / 'allocation_canonical7f/SOURCES.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == SOURCES_SHA
    record = json.loads(data)[name]
    data = (ROOT / record['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == record['file_sha256']
    raw = json.loads(data)
    if 'index' in record:
        raw = raw[record['index']]
    assert raw['name'] == name and raw['object'] == 'card'
    assert raw['id'] == record['id'] and raw['oracle_id'] == record['oracle_id']
    return raw


def expected_card(name):
    raw = raw_card(name)
    normalized = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    entry = {**raw, **normalized, 'card_name': name, 'quantity': 8,
             'colors': raw['colors'], 'card_faces': json.loads(normalized['card_faces_json'])}
    state = MatchFactory.from_decks([entry], [], seed=0)
    return next(card for card in state.cards.values() if card.zone == Zone.LIBRARY)


def capture(case, monkeypatch):
    name, body = case
    consumer = RulesEngine.legal_moves
    captured = []

    def observe(self, state, *args, **kwargs):
        matches = [card for card in state.cards.values() if card.name == name]
        if matches:
            captured.append(matches[0])
            raise Consumed
        return consumer(self, state, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(RulesEngine, 'legal_moves', observe)
        with pytest.raises(Consumed):
            body()
    assert len(captured) == 1
    return captured[0]


@pytest.mark.parametrize('case', CASES, ids=[case[0] for case in CASES])
def test_actual_original_first_legal_consumer_has_complete_printed_facts(case, monkeypatch):
    actual = capture(case, monkeypatch)
    expected = expected_card(case[0])
    different = sorted(field for field in PRINTED
                       if getattr(actual, field) != getattr(expected, field))
    assert not different, (case[0], different)
    runtime = CardInstance(id=actual.id, name='Anonymous runtime-default protocol',
                           owner=actual.owner, controller=actual.controller,
                           zone=actual.zone, summoning_sick=actual.zone != Zone.BATTLEFIELD)
    if case[0] == 'Phantom Nishoba':
        runtime.counters = {'+1/+1': 7}
        runtime.counter_timestamps = {'+1/+1': 1}
    assert all(getattr(actual, field.name) == getattr(runtime, field.name)
               for field in fields(CardInstance) if field.name not in PRINTED)


def test_complete_official_sources_are_pinned_and_independently_mutable():
    records = json.loads((ROOT / 'allocation_canonical7f/SOURCES.json').read_bytes())
    for name, record in records.items():
        first, second = raw_card(name), raw_card(name)
        assert first == second and first is not second and len(first) > 40
        assert first['legalities'] and first['rulings_uri'].startswith('https://api.scryfall.com/')
        first['legalities'].clear()
        assert second['legalities'] and raw_card(name) == second
        if 'provenance' in record:
            assert hashlib.sha256((ROOT / record['provenance']).read_bytes()).hexdigest() == record['provenance_sha256']
        else:
            assert record['bulk_sha256'] == '17cf0c4d0c96dde18337326626037732d0ff219c498d19ef0c9536f6db62dc13'


def test_original_nishoba_pose_uses_native_entry_counters_not_forged_printed_power(monkeypatch):
    card = capture(CASES[0], monkeypatch)
    assert raw_card('Phantom Nishoba')['power'] == raw_card('Phantom Nishoba')['toughness'] == '0'
    assert card.counters == {'+1/+1': 7} and card.owner == card.controller == 1
    assert card.id == 'friendly' and card.zone == Zone.BATTLEFIELD and not card.summoning_sick


def test_original_instances_do_not_share_mutable_containers(monkeypatch):
    first, second = capture(CASES[3], monkeypatch), capture(CASES[3], monkeypatch)
    before = deepcopy(vars(second))
    first.types.append('Noncanonical independence protocol')
    first.counters['independence-protocol'] = 1
    assert vars(second) == before and first is not second
