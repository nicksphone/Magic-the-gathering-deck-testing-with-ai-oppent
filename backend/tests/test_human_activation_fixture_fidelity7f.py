"""Observe actual original activation sources before their existing consumers."""
from copy import deepcopy
from dataclasses import fields
import hashlib
import json
from pathlib import Path

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine import oracle_effects
from rules_engine.engine import RulesEngine
from tests import test_human_action_safety as original
from tests.library_canonical_fixtures import PRINTED


ROOT = Path(__file__).parent / 'fixtures'
SOURCE_SHA = '8b4dcb302d0a2f65b2d44e274205179b08f8759520cbc852ef18c91127ea0a5a'
CASES = [
    ('Prodigal Pyromancer', original.test_activated_target_validation_happens_before_paying_tap_cost,
     RulesEngine, 'take_action', False),
    ('Oona, Queen of the Fae', original.test_unsupported_activation_is_rejected_without_paying_costs,
     RulesEngine, 'legal_moves', False),
    ('Azure Mage', original.test_activated_extractor_preserves_adjacent_mana_symbols,
     oracle_effects, 'extract_activated_abilities', True),
]


class Consumed(BaseException):
    pass


def raw_card(name):
    data = (ROOT / 'human_activation_canonical7f/SOURCES.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == SOURCE_SHA
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
    name, body, owner, seam, _ = case
    consumer = getattr(owner, seam)
    captured = []

    def observe(*args, **kwargs):
        if owner is RulesEngine:
            matches = [card for card in args[1].cards.values() if card.name == name]
        else:
            matches = [args[0]] if args[0].name == name else []
        if matches:
            captured.append(matches[0])
            raise Consumed
        return consumer(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(owner, seam, observe)
        with pytest.raises(Consumed):
            body()
    assert len(captured) == 1
    return captured[0]


@pytest.mark.parametrize('case', CASES, ids=[case[0] for case in CASES])
def test_original_source_has_full_printed_facts_and_exact_runtime_defaults(case, monkeypatch):
    actual = capture(case, monkeypatch)
    expected = expected_card(case[0])
    differences = sorted(field for field in PRINTED
                         if getattr(actual, field) != getattr(expected, field))
    assert not differences, (case[0], differences)
    # An anonymous schema-only control, not replacement canonical evidence.
    runtime = CardInstance(id=actual.id, name='Anonymous runtime-default protocol',
                           owner=1, controller=1, zone=Zone.BATTLEFIELD,
                           summoning_sick=case[4])
    assert all(getattr(actual, field.name) == getattr(runtime, field.name)
               for field in fields(CardInstance) if field.name not in PRINTED)


def test_complete_sources_are_pinned_fresh_and_provenance_is_retained():
    records = json.loads((ROOT / 'human_activation_canonical7f/SOURCES.json').read_bytes())
    for name, record in records.items():
        first, second = raw_card(name), raw_card(name)
        assert len(first) > 40 and first == second and first is not second
        assert first['legalities'] and first['rulings_uri'].startswith('https://api.scryfall.com/')
        first['legalities'].clear()
        assert second['legalities'] and raw_card(name) == second
        if 'provenance' in record:
            assert hashlib.sha256((ROOT / record['provenance']).read_bytes()).hexdigest() == record['provenance_sha256']
        else:
            assert record['bulk_sha256'] == '17cf0c4d0c96dde18337326626037732d0ff219c498d19ef0c9536f6db62dc13'
            assert record['source_line'] > 0


def test_actual_original_sources_and_their_mutables_are_independent(monkeypatch):
    first, second = capture(CASES[0], monkeypatch), capture(CASES[0], monkeypatch)
    before = deepcopy(vars(second))
    first.types.append('Noncanonical independence protocol')
    first.counters['independence-protocol'] = 1
    assert vars(second) == before and first is not second
