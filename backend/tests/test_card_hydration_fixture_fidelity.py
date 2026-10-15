"""Canonical positive fixtures and explicit missing-metadata protocol boundaries."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode

import pytest

import tests.test_card_hydration as original
from card_data.sync import ScryfallSyncService


FIXTURES = Path(__file__).parent / 'fixtures'
PINS = {
    'knowledge_profiles/seed155-scryfall.jsonl': '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732',
    'canonical_hydration/figure-of-destiny-scryfall-raw.json': '861c21c299816724a667c392cc37d4182da2a52496e1cb7da5f6cf39a97edaeb',
    'canonical_hydration/valki-scryfall-raw.json': 'ae2bb42378419e9b961eff2f27c7a4c2b7b4ec4af0b72dc3ce7bf4b8a7f87f86',
    'canonical_hydration/ruination-guide-scryfall-raw.json': '6ea0ba3ff8ffee7604b34eee796a2a54bb78028e6def9b48e060449b8dbff067',
}
VALKI = 'Valki, God of Lies // Tibalt, Cosmic Impostor'
SUBJECTS = [
    ('Skewer the Critics', original.test_hydration_preserves_cached_noncreature_type_before_match_factory),
    ('Figure of Destiny', original.test_cached_hybrid_colors_survive_live_hydration_and_snapshot),
    (VALKI, original.test_selected_modal_face_uses_its_own_canonical_colors),
]


def archived(name):
    if name == 'Skewer the Critics':
        return next(json.loads(line) for line in
                    (FIXTURES / 'knowledge_profiles/seed155-scryfall.jsonl').read_text().splitlines()
                    if json.loads(line)['name'] == name)
    filename = {
        'Figure of Destiny': 'figure-of-destiny', VALKI: 'valki',
        'Ruination Guide': 'ruination-guide',
    }[name] + '-scryfall-raw.json'
    return json.loads((FIXTURES / 'canonical_hydration' / filename).read_bytes())


def capture_actual(monkeypatch, name, body):
    captured = []

    class BeforeUse(Exception):
        pass

    def capture_row(repo, deck):
        captured.append(repo.rows[name.lower()])
        raise BeforeUse

    def capture_face(card):
        captured.append(card)
        raise BeforeUse

    with monkeypatch.context() as patch:
        patch.setattr(original, 'hydrate_deck_cards', capture_row)
        patch.setattr(original, 'card_color_names', capture_face)
        with pytest.raises(BeforeUse):
            body()
    assert len(captured) == 1
    return captured[0]


@pytest.mark.parametrize('name,body', SUBJECTS, ids=['Skewer', 'Figure', 'Valki'])
def test_actual_positive_uses_complete_canonical_projection(name, body, monkeypatch):
    actual = capture_actual(monkeypatch, name, body)
    raw = archived(name)
    expected = ({**raw, 'selected_face_index': 0} if name == VALKI else
                ScryfallSyncService._normalize_payload(raw, '/card-images/canonical-hydration-fixture.svg'))
    assert vars(actual) == expected, 'Actual positive fixture is truncated or not canonical'


def test_missing_metadata_is_explicit_but_devoid_text_is_complete(monkeypatch):
    captured = []
    real_colors = original.card_color_names

    def capture(card):
        captured.append(deepcopy(vars(card)))
        return real_colors(card)

    monkeypatch.setattr(original, 'card_color_names', capture)
    original.test_missing_color_metadata_uses_hybrid_cost_but_devoid_is_colorless()
    assert captured == [
        dict(mana_cost=archived('Figure of Destiny')['mana_cost'], oracle_text='', colors=None, card_faces=[]),
        dict(mana_cost=archived('Ruination Guide')['mana_cost'],
             oracle_text=archived('Ruination Guide')['oracle_text'], colors=None, card_faces=[]),
    ]


def test_official_raw_bytes_and_provenance_are_complete():
    for filename, pin in PINS.items():
        assert hashlib.sha256((FIXTURES / filename).read_bytes()).hexdigest() == pin
    seed = json.loads((FIXTURES / 'knowledge_profiles/PROVENANCE.json').read_bytes())
    assert seed['snapshot_sha256'] == PINS['knowledge_profiles/seed155-scryfall.jsonl']
    assert seed['raw_objects'] == 155 and seed['oracle_modified'] is False
    provenance = json.loads((FIXTURES / 'canonical_hydration/PROVENANCE.json').read_bytes())
    assert provenance['minimum_request_spacing_seconds'] >= 0.5
    expected = [('Figure of Destiny', 'Figure of Destiny'), ('Valki, God of Lies', VALKI),
                ('Ruination Guide', 'Ruination Guide')]
    assert [(r['requested_name'], r['canonical_parent']) for r in provenance['records']] == expected
    for receipt in provenance['records']:
        raw = archived(receipt['canonical_parent'])
        assert receipt['http_status'] == 200 and receipt['oracle_modified'] is False
        assert receipt['url'] == 'https://api.scryfall.com/cards/named?' + urlencode({'exact': receipt['requested_name']})
        assert receipt['sha256'] == PINS['canonical_hydration/' + receipt['file']]
        assert receipt['utc_started'] and receipt['utc_completed']
        assert raw['object'] == 'card' and raw['lang'] == 'en'
        assert raw['name'] == receipt['canonical_parent'] and raw['id'] == receipt['scryfall_id']
        assert raw['oracle_id'] == receipt['oracle_id'] and raw['legalities']
        assert raw['uri'] == 'https://api.scryfall.com/cards/' + raw['id']
        assert raw['rulings_uri'].startswith('https://api.scryfall.com/cards/')
    valki = archived(VALKI)
    assert valki['layout'] == 'modal_dfc'
    assert [f['name'] for f in valki['card_faces']] == ['Valki, God of Lies', 'Tibalt, Cosmic Impostor']
    assert [f['colors'] for f in valki['card_faces']] == [['B'], ['B', 'R']]
    assert all(f['oracle_text'] and f['mana_cost'] and f['type_line'] for f in valki['card_faces'])


def test_actual_objects_are_fresh_and_do_not_mutate_archives(monkeypatch):
    before = {filename: (FIXTURES / filename).read_bytes() for filename in PINS}
    for name, body in SUBJECTS:
        first = capture_actual(monkeypatch, name, body)
        expected = deepcopy(vars(first))
        first.oracle_text = 'Deliberate noncanonical independence sentinel'
        if getattr(first, 'card_faces', None):
            first.card_faces[0]['colors'].append('G')
        second = capture_actual(monkeypatch, name, body)
        assert second is not first and vars(second) == expected
    assert {filename: (FIXTURES / filename).read_bytes() for filename in PINS} == before
