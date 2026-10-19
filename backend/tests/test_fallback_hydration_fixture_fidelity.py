"""Canonical cache-fixture fidelity, not HTTP, SQL or gameplay qualification."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from card_data.sync import ScryfallSyncService
import tests.test_fallback_hydration as original
from tests.test_knowledge_ingest import _official_card
from tests.test_knowledge_ingest_fixture_fidelity import archived_card


NAME = 'Delver of Secrets // Insectile Aberration'
IMAGES = ('/card-images/delver-front.png', '/card-images/delver-back.png')


def capture_cache_row(monkeypatch):
    captured = []

    class CapturedBeforeHydration(Exception):
        pass

    def capture(repo, deck):
        assert deck == [{'quantity': 1, 'card_name': 'Delver of Secrets'}]
        rows = repo.get_cached_cards_by_names(['Delver of Secrets'])
        captured.append(rows['delver of secrets'])
        raise CapturedBeforeHydration

    monkeypatch.setattr(original, '_hydrate_deck_cards', capture)
    with pytest.raises(CapturedBeforeHydration):
        original.test_hydrate_deck_cards_uses_face_image_when_root_image_missing(monkeypatch)
    assert len(captured) == 1
    return captured[0]


def test_actual_delver_cache_row_matches_complete_canonical_projection(monkeypatch):
    raw = archived_card(NAME)
    before = deepcopy(raw)
    expected = ScryfallSyncService._normalize_payload(raw, IMAGES[0])
    expected['image_uri'] = None
    faces = json.loads(expected['card_faces_json'])
    for face, image in zip(faces, IMAGES):
        face['image_uri'] = image
    expected['card_faces_json'] = json.dumps(faces)

    actual = capture_cache_row(monkeypatch)
    assert vars(actual) == expected, 'Actual cached Delver fixture is not the canonical projection'
    assert raw == before
    assert [face['name'] for face in faces] == [face['name'] for face in raw['card_faces']]
    assert [face['oracle_text'] for face in faces] == [face['oracle_text'] for face in raw['card_faces']]


def test_pinned_official_loader_matches_provenance_and_returns_fresh_objects():
    path = Path(__file__).parent / 'fixtures/knowledge_profiles/seed155-scryfall.jsonl'
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    expected = archived_card(NAME)
    first, second = _official_card(NAME), _official_card(NAME)
    assert first == second == expected
    assert first is not second and first['card_faces'] is not second['card_faces']
    assert all(left is not right for left, right in zip(first['card_faces'], second['card_faces']))
    first['card_faces'][0].clear()
    assert second == expected and _official_card(NAME) == expected
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_actual_cache_fixture_returns_fresh_rows_and_face_payloads(monkeypatch):
    first, second = capture_cache_row(monkeypatch), capture_cache_row(monkeypatch)
    before = deepcopy(vars(second))
    assert first is not second and vars(first) == before
    faces = json.loads(first.card_faces_json)
    faces[0].clear()
    first.card_faces_json = json.dumps(faces)
    first.oracle_text = ''
    assert vars(second) == before
    assert vars(capture_cache_row(monkeypatch)) == before
