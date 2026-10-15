"""Actual positive builders versus pinned RAW; no invented Oracle or outcomes."""
import hashlib
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from card_data.sync import ScryfallSyncService
from tests import canonical_positive_fixtures as canonical
import tests.test_card_image_sync as images
import tests.test_deck_analysis as decks


DECK_CASES = [getattr(decks, name) for name in (
    'test_guess_archetype_uses_curve_and_damage_density_for_burn',
    'test_guess_archetype_uses_metadata_for_control_shell',
    'test_deck_land_count_ignores_mana_creatures_and_land_text',
    'test_modal_back_face_types_do_not_distort_front_face_deck_shape',
    'test_guess_archetype_detects_tokens_from_metadata_and_text',
    'test_guess_archetype_reads_split_cards_from_combined_face_costs')]
CACHE_CASES = [
    ('Old Fogey', images.test_completeness_report_warns_for_unsupported_bands_with_other),
    ('Benalish Hero', images.test_completeness_report_warns_for_unsupported_bands_with_other),
    ('Grizzly Bears', images.test_cached_vanilla_creature_has_valid_empty_oracle_text),
    ('Willbender', images.test_completeness_report_warns_for_morph),
]


def archived(name):
    source = canonical.SOURCES.get(name, canonical.SEED)
    data = (canonical.FIXTURES / source).read_bytes()
    assert hashlib.sha256(data).hexdigest() == canonical.PINS[source]
    rows = ([json.loads(line) for line in data.splitlines()] if source.endswith('.jsonl')
            else json.loads(data))
    if type(rows) is dict:
        rows = [rows]
    matches = [row for row in rows if row.get('name') == name or any(
        face.get('name') == name for face in row.get('card_faces', []))]
    assert len(matches) == 1 and matches[0].get('object') == 'card'
    return matches[0]


@pytest.mark.parametrize('body', DECK_CASES, ids=lambda body: body.__name__)
def test_actual_named_deck_positive_objects_are_complete_raw(body, monkeypatch):
    captured = []

    class BeforeAnalysis(Exception):
        pass

    def capture(deck):
        captured.append(deck)
        raise BeforeAnalysis

    monkeypatch.setattr(decks, 'analyze_deck', capture)
    with pytest.raises(BeforeAnalysis):
        body()
    assert len(captured) == 1
    actual = {entry['card_name']: entry['card_metadata'] for entry in captured[0]}
    expected = {name: archived(name) for name in actual}
    assert actual == expected, 'Actual positive deck builder contains incomplete or handwritten card facts'


@pytest.mark.parametrize('name,body', CACHE_CASES, ids=[name for name, _ in CACHE_CASES])
def test_actual_named_cache_positive_is_canonical_projection(name, body, monkeypatch):
    captured = []

    class BeforeReport(Exception):
        pass

    def capture(service, requested):
        rows = service.repo.get_cached_cards_by_names(requested)
        captured.append(rows[name.lower()])
        raise BeforeReport

    monkeypatch.setattr(images.CardService, 'completeness_report', capture)
    with pytest.raises(BeforeReport):
        body()
    assert len(captured) == 1
    expected = ScryfallSyncService._normalize_payload(archived(name), canonical.CACHED_IMAGE_URI)
    assert vars(captured[0]) == expected, 'Actual named cache fixture is not the full canonical projection'


def test_official_intake_and_existing_provenance_bind_unchanged_complete_bytes():
    root = canonical.FIXTURES
    provenance = (root / 'canonical_positive_batch/PROVENANCE.json').read_bytes()
    assert hashlib.sha256(provenance).hexdigest() == '1f3aef735c08cedcf03f2d26620a5b20ef8a5b1470ff40a3726b00c1f612ae77'
    receipt = json.loads(provenance)
    assert receipt['complete'] is True and receipt['oracle_modified'] is False
    assert len(receipt['records']) == receipt['request_budget'] == 6
    assert receipt['art_or_rulings_requests'] == 0
    for index, record in enumerate(receipt['records']):
        data = (root / 'canonical_positive_batch' / record['file']).read_bytes()
        raw = json.loads(data)
        assert record['status'] == 200 and record['response_url'] == record['url']
        assert urlsplit(record['url']).netloc == 'api.scryfall.com'
        assert parse_qs(urlsplit(record['url']).query) == {'exact': [record['requested_name']]}
        assert hashlib.sha256(data).hexdigest() == record['raw_sha256']
        assert len(data) == record['bytes']
        assert raw['name'] == record['requested_name'] and raw['id'] == record['scryfall_id']
        assert raw['oracle_id'] == record['oracle_id'] and raw['object'] == 'card'
        assert record['started_utc'] and record['finished_utc'] and record['headers']
        if index:
            assert record['start_spacing_seconds'] >= .5
    seed = json.loads((root / 'knowledge_profiles/PROVENANCE.json').read_bytes())
    assert seed['snapshot_sha256'] == canonical.PINS[canonical.SEED] and seed['oracle_modified'] is False
    hydration = json.loads((root / 'canonical_hydration/PROVENANCE.json').read_bytes())
    valki = next(row for row in hydration['records'] if row['canonical_parent'].startswith('Valki,'))
    assert valki['http_status'] == 200 and valki['oracle_modified'] is False
    assert valki['sha256'] == canonical.PINS[canonical.SOURCES[valki['canonical_parent']]]
    bala = json.loads((root / 'graveyard_permissions/bala-ged-recovery.json.provenance.json').read_bytes())
    assert bala['sha256'] == canonical.PINS[canonical.SOURCES['Bala Ged Recovery // Bala Ged Sanctuary']]
    assert bala['source'].startswith('https://api.scryfall.com/cards/named?exact=')
    assert bala['retrieved_at']
    for source, pin in canonical.PINS.items():
        assert hashlib.sha256((root / source).read_bytes()).hexdigest() == pin


def test_shared_loader_returns_fresh_complete_objects_without_editing_sources():
    names = [*canonical.SOURCES, 'Wedding Announcement', 'Delver of Secrets // Insectile Aberration']
    for name in names:
        expected = archived(name)
        first, second = canonical.raw_card(name), canonical.raw_card(name)
        assert first == second == expected and first is not second
        first.clear()
        assert second == expected and canonical.raw_card(name) == expected


def test_split_deck_face_counts_come_from_full_raw_and_actual_quantities(monkeypatch):
    captured = []

    class BeforeAnalysis(Exception):
        pass

    def capture(deck):
        captured.append(deck)
        raise BeforeAnalysis

    monkeypatch.setattr(decks, 'analyze_deck', capture)
    with pytest.raises(BeforeAnalysis):
        decks.test_guess_archetype_reads_split_cards_from_combined_face_costs()
    assert len(captured) == 1
    quantities = {entry['card_name']: entry['quantity'] for entry in captured[0]}
    assert quantities['Fire // Ice'] == quantities['Wedding Announcement'] == 4
    fire, wedding = archived('Fire // Ice'), archived('Wedding Announcement')
    assert len(fire['card_faces']) == len(wedding['card_faces']) == 2
    assert fire['layout'] == 'split' and wedding['layout'] == 'transform'
    expected_face_copies = sum(entry['quantity'] for entry in captured[0]
                               if len(archived(entry['card_name']).get('card_faces', [])) > 1)
    expected_split_copies = sum(entry['quantity'] for entry in captured[0]
                                if archived(entry['card_name'])['layout'] == 'split')
    assert expected_face_copies == 8
    assert expected_split_copies == 4
