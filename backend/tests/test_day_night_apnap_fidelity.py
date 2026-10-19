"""Inspect the original APNAP test's actual objects before its first transition."""
from copy import deepcopy
import hashlib
import json

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import Zone, _infer_keywords
from rules_engine.card_types import printed_card_types
from tests import test_day_night as original
from tests.day_night_apnap_canonical import (
    CATHAR, DIRECTORY, DISPLAY_IMAGE, PROVENANCE_SHA, SEED, SEED_SHA, SOURCES, raw_card,
)


class BeforeUntap(BaseException):
    pass


def captured_source_objects(monkeypatch):
    captured = []
    def before_untap(state, engine):
        captured.append(state)
        raise BeforeUntap()
    with monkeypatch.context() as patch:
        patch.setattr(original, '_untap_then_upkeep', before_untap)
        with pytest.raises(BeforeUntap):
            original.test_simultaneous_day_night_transforms_share_apnap_trigger_order_window(patch)
    assert len(captured) == 1
    return captured[0]


def assert_complete(card, name):
    raw = raw_card(name)
    cached = ScryfallSyncService._normalize_payload(raw, DISPLAY_IMAGE)
    faces = ScryfallSyncService._normalize_faces(raw.get('card_faces') or [])
    surface = raw['card_faces'][0] if faces else raw
    assert card.name == surface['name']
    assert card.card_faces == faces
    assert card.oracle_text == surface.get('oracle_text', '')
    assert card.mana_cost == surface.get('mana_cost', '')
    assert card.type_line == surface['type_line']
    assert card.types == printed_card_types(surface['type_line'])
    assert card.layout == raw['layout']
    assert card.colors == surface.get('colors', [])
    assert card.keywords == _infer_keywords(surface.get('oracle_text', ''))
    for field in ('power', 'toughness', 'loyalty'):
        value = surface.get(field)
        assert getattr(card, field) == (int(value) if value is not None else None)
        if field != 'loyalty':
            assert getattr(card, 'printed_' + field) == value
    assert card.selected_face_index == (0 if faces else None)
    assert card.image_uri == (faces[0]['image_uri'] if faces else cached['image_uri'])


def test_full_official_raw_and_provenance_pins_are_retained():
    data = (DIRECTORY / 'PROVENANCE.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == PROVENANCE_SHA
    provenance = json.loads(data)
    assert hashlib.sha256(SEED.read_bytes()).hexdigest() == SEED_SHA
    assert provenance['existing_cathar']['sha256'] == SEED_SHA
    for entry in provenance['new_cards']:
        file, pin = SOURCES[entry['name']]
        payload = (DIRECTORY / file).read_bytes()
        assert entry['file'] == file and entry['sha256'] == pin
        assert hashlib.sha256(payload).hexdigest() == pin
        raw = json.loads(payload)
        assert raw['object'] == 'card' and raw['id'] == entry['scryfall_id']
        assert raw['oracle_id'] == entry['oracle_id'] and raw['uri'] == entry['canonical_uri']
        assert entry['full_unmodified_https_response'] is True
    cathar = raw_card(CATHAR)
    assert [face['name'] for face in cathar['card_faces']] == ['Brutal Cathar', 'Moonrage Brute']
    assert 'exile' in cathar['card_faces'][0]['oracle_text'].lower()
    assert 'ward' in cathar['card_faces'][1]['oracle_text'].lower()


@pytest.mark.parametrize('name,owner,ids', [
    ('Phyrexian Arena', 1, ['arena']),
    ('Corruption of Towashi', 1, ['corruption-1']),
    ('Corruption of Towashi', 2, ['corruption-2']),
    (CATHAR, 1, ['cathar-1-1', 'cathar-1-2']),
    (CATHAR, 2, ['cathar-2-1', 'cathar-2-2']),
])
def test_actual_original_source_objects_are_complete_before_untap(monkeypatch, name, owner, ids):
    state = captured_source_objects(monkeypatch)
    for card_id in ids:
        card = state.cards[card_id]
        assert card.id == card_id and card.owner == card.controller == owner
        assert card.zone == Zone.BATTLEFIELD and card_id in state.players[owner].battlefield
        assert_complete(card, name)


def test_actual_source_faces_are_fresh_per_copy_and_per_setup(monkeypatch):
    first = captured_source_objects(monkeypatch)
    second = captured_source_objects(monkeypatch)
    left = first.cards['cathar-1-1']
    sibling = first.cards['cathar-2-2']
    other = second.cards['cathar-1-1']
    assert left.card_faces is not sibling.card_faces and left.card_faces is not other.card_faces
    assert left.card_faces[1] is not sibling.card_faces[1]
    before = deepcopy((sibling.card_faces, other.card_faces, raw_card(CATHAR)))
    left.card_faces[1]['oracle_text'] = 'MUTATED PROTOCOL ONLY'
    assert (sibling.card_faces, other.card_faces, raw_card(CATHAR)) == before


@pytest.mark.parametrize('name,card_id', [(CATHAR, 'cathar-1-1'), ('Corruption of Towashi', 'corruption-2')])
def test_fidelity_rejects_dropped_face_or_oracle_paragraph(monkeypatch, name, card_id):
    state = captured_source_objects(monkeypatch)
    card = deepcopy(state.cards[card_id])
    if name == CATHAR:
        card.card_faces = card.card_faces[:1]
    else:
        card.oracle_text = card.oracle_text.splitlines()[0]
    with pytest.raises(AssertionError):
        assert_complete(card, name)
