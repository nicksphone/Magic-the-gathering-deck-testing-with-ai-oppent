"""Capture genuine fixture inputs at trusted transform seams, not cast history."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

import tests.test_transform_numeric_ai as original
from tests.canonical_positive_fixtures import raw_card


KUMANO = 'Kumano Faces Kakkazan // Etching of Kumano'
DELVER = 'Delver of Secrets // Insectile Aberration'
SEED_SHA = '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
RAW_PINS = {
    KUMANO: '3080b71a13e58974f1f9c1fb31221f5026d411dd8bc948ee4f69d1f24ab3a124',
    DELVER: '531fa0962e66615439bf0aabcf58835acaa60fee9e10ba5f319f1cb3347766ae',
    'Lightning Bolt': 'feb321842f2c0fefc8102ce0fd3cf7e37137f5ff90af282ef6086fafad4ee834',
}
SUBJECTS = [
    (KUMANO, original.test_kumano_transforms_to_numeric_creature_and_ai_can_assess_it, 'transform_card'),
    (DELVER, original.test_revealed_instant_transforms_delver_to_numeric_flying_face, 'transform_if_top_matches'),
]


def capture(monkeypatch, body, seam):
    real = getattr(original, seam)
    records = []

    def observe(state, player, payload):
        card = state.cards[payload['target_card_id']]
        top = state.cards[state.players[player].library[-1]]
        records.append(dict(source=deepcopy(vars(card)), top=deepcopy(vars(top)), actual_source=card))
        return real(state, player, payload)

    with monkeypatch.context() as patch:
        patch.setattr(original, seam, observe)
        body()
    assert len(records) == 1
    return records[0]


@pytest.mark.parametrize('name,body,seam', SUBJECTS, ids=['Kumano', 'Delver'])
def test_actual_transform_source_has_complete_canonical_faces_and_front(name, body, seam, monkeypatch):
    source = capture(monkeypatch, body, seam)['source']
    raw = raw_card(name)
    front = raw['card_faces'][0]
    assert source['card_faces'] == raw['card_faces'], 'Actual source has shortened or handwritten faces'
    assert source['layout'] == raw['layout']
    for key in ('name', 'oracle_text', 'mana_cost', 'type_line', 'colors'):
        assert source[key] == front[key]
    for key in ('power', 'toughness', 'loyalty'):
        expected = int(front[key]) if front.get(key) is not None else None
        assert source[key] == expected
    assert source['owner'] == source['controller'] == 1
    assert source['zone'] == original.Zone.BATTLEFIELD


def test_actual_top_before_delver_transform_is_complete_bolt_not_renamed_land(monkeypatch):
    top = capture(monkeypatch, SUBJECTS[1][1], SUBJECTS[1][2])['top']
    raw = raw_card('Lightning Bolt')
    for key in ('name', 'oracle_text', 'mana_cost', 'type_line', 'colors', 'layout'):
        assert top[key] == raw[key], 'Actual top is not the canonical instant'
    assert top['types'] == ['Instant'] and top['card_faces'] == []
    assert top['power'] is None and top['toughness'] is None
    assert top['owner'] == 1 and top['zone'] == original.Zone.LIBRARY


def test_real_seam_objects_and_nested_faces_are_independent(monkeypatch):
    for name, body, seam in SUBJECTS:
        first = capture(monkeypatch, body, seam)
        expected = deepcopy(first['source'])
        first['actual_source'].card_faces[0]['oracle_text'] = 'Declared noncanonical independence sentinel'
        second = capture(monkeypatch, body, seam)
        assert second['actual_source'] is not first['actual_source']
        assert second['source'] == expected
    for name in RAW_PINS:
        raw = raw_card(name)
        assert hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == RAW_PINS[name]


def test_complete_official_rows_match_pinned_seed_and_provenance():
    root = Path(__file__).parent / 'fixtures/knowledge_profiles'
    seed = (root / 'seed155-scryfall.jsonl').read_bytes()
    assert hashlib.sha256(seed).hexdigest() == SEED_SHA
    provenance = json.loads((root / 'PROVENANCE.json').read_bytes())
    assert provenance['snapshot_sha256'] == SEED_SHA
    assert provenance['raw_objects'] == 155 and provenance['oracle_modified'] is False
    rows = {row['name']: row for row in map(json.loads, seed.splitlines())}
    for name, pin in RAW_PINS.items():
        raw = raw_card(name)
        assert raw == rows[name] and raw['object'] == 'card'
        assert raw['id'] and raw['oracle_id'] and raw['legalities']
        assert raw['rulings_uri'].startswith('https://api.scryfall.com/cards/')
        assert hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == pin
        if name != 'Lightning Bolt':
            assert len(raw['card_faces']) == 2 and raw['layout'] == 'transform'
            assert all(face['oracle_text'] for face in raw['card_faces'])
