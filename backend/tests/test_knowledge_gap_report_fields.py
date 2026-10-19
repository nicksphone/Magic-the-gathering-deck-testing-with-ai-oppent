"""Coverage facts, not gameplay/image-quality certification or stock repairs."""
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import knowledge_gap_report as gap


class Rows:
    """Inert projection fixture; real repository acceptance is separately tested."""
    def __init__(self, knowledge=(), cards=()):
        self.knowledge, self.cards = list(knowledge), list(cards)

    def list_card_knowledge(self):
        return self.knowledge

    def list_cards(self):
        return self.cards

    def get_cached_cards_by_names(self, names):
        return {name.strip().lower(): card for name in names for card in self.cards
                if name.casefold() == card.name.casefold()}


def knowledge(name='Diagnostic', *, source='scryfall', text='Draw a card.', **profile):
    raw = {'name': name, 'oracle_id': 'oracle', 'oracle_text': text,
           'type_line': 'Sorcery'}
    return SimpleNamespace(name=name, oracle_source=source,
                           profiles_json=json.dumps({'card_data': raw, **profile}))


def cached(name='Diagnostic', *, text='Draw a card.', image=None, faces=()):
    return SimpleNamespace(name=name, oracle_text=text, image_uri=image,
                           card_faces_json=json.dumps(list(faces)))


def report(repo, names=('Diagnostic',), **kwargs):
    try:
        return gap.knowledge_report(repo, list(names), **kwargs)
    except TypeError as error:
        pytest.fail('Coverage binding rejected declared inputs: ' + str(error))


def field(row, key):
    assert key in row, 'Missing declared coverage field: ' + key
    return row[key]


def test_persisted_source_and_physical_cache_are_separate_facts():
    for source in ('scryfall', 'manual', '', 'external-unknown'):
        result = report(Rows([knowledge(source=source)], [cached()]))
        row = result['cards'][0]
        assert field(row, 'oracle_source') == source
        assert field(row, 'knowledge_present') is True
        assert field(row, 'cached') is True
        assert row['canonical'] is (source == 'scryfall')
        assert result['database']['cached_rows'] == 1
    missing = report(Rows(cards=[cached()]))['cards'][0]
    assert field(missing, 'oracle_source') is None
    assert field(missing, 'knowledge_present') is False
    assert field(missing, 'cached') is True
    assert missing['canonical'] is False
    bulk = report(Rows([knowledge()]))['cards'][0]
    assert field(bulk, 'cached') is False
    assert bulk['canonical'] is True


@pytest.mark.parametrize('text, expected', [('', True), ('  ', True), ('Flying', False),
                                           (None, None), (7, None)])
def test_blank_canonical_surface_is_not_missing_or_repaired_by_cache(text, expected):
    row = report(Rows([knowledge(text=text)], [cached(text='Nonblank cache')]))['cards'][0]
    assert field(row, 'oracle_text_blank') is expected
    assert field(row, 'cache_oracle_text_blank') is False
    assert row['canonical'] is True


@pytest.mark.parametrize('text, expected', [('', True), ('Draw', False), (None, None), (1, None)])
def test_raw_cached_text_is_never_filled_from_canonical_or_seed(text, expected):
    row = report(Rows([knowledge()], [cached(text=text)]))['cards'][0]
    assert field(row, 'cache_oracle_text_blank') is expected
    assert field(row, 'oracle_text_blank') is False


def test_face_blankness_uses_requested_surface_and_unknown_not_zero():
    row = knowledge('Front // Back', text=None)
    profile = json.loads(row.profiles_json)
    profile['card_data']['card_faces'] = [
        {'name': 'Front', 'oracle_text': ''}, {'name': 'Back', 'oracle_text': 'Flying'}]
    row.profiles_json = json.dumps(profile)
    result = report(Rows([row]), ['Front', 'Back', 'Front // Back'])
    values = {entry['name']: field(entry, 'oracle_text_blank') for entry in result['cards']}
    assert values == {'Front': True, 'Back': False, 'Front // Back': False}
    del profile['card_data']['card_faces'][1]['oracle_text']
    row.profiles_json = json.dumps(profile)
    result = report(Rows([row]), ['Front', 'Back', 'Front // Back'])
    values = {entry['name']: field(entry, 'oracle_text_blank') for entry in result['cards']}
    assert values == {'Front': True, 'Back': None, 'Front // Back': None}


@pytest.mark.parametrize('verified', ['false', 'true', 1, {}, [True]])
def test_only_literal_true_verifies_rulings(verified):
    result = report(Rows([knowledge(rulings_verified=verified, rulings=[])]))
    assert result['cards'][0]['rulings_verified'] is False
    assert result['rulings_pending'] == ['Diagnostic']
    assert result['database']['rulings_verified'] == 0


def test_verified_empty_rulings_and_populated_unverified_remain_distinct():
    result = report(Rows([knowledge(rulings_verified=True, rulings=[])]))
    assert result['cards'][0]['rulings_verified'] is True
    assert result['cards'][0]['rulings_count'] == 0
    assert result['rulings_pending'] == []
    row = report(Rows([knowledge(rulings_verified=False, rulings=[{'comment': 'x'}])]))['cards'][0]
    assert row['rulings_verified'] is False and row['rulings_count'] == 1


@pytest.mark.parametrize('profile', ['bad-json', '[]', 'null', '{"card_data": []}',
    '{"card_data": {"card_faces": [null]}}', '{"rulings": "not-a-list"}',
    '{"card_data": {"card_faces": "bad"}}'])
def test_malformed_profile_shapes_fail_explicitly_without_mutation(profile):
    row = knowledge()
    row.profiles_json = profile
    with pytest.raises(ValueError):
        gap.knowledge_report(Rows([row]), ['Diagnostic'])
    assert row.profiles_json == profile


def test_omitted_image_binding_is_unknown_not_ambient_probe():
    row = report(Rows([knowledge()], [cached(image='/card-images/example.jpg')]))['cards'][0]
    assert field(row, 'local_image') is None
    assert field(row, 'image_status') == 'unavailable'


@pytest.mark.parametrize('uri, expected', [('/card-images/real.jpg', (True, 'local')),
    ('/card-images/placeholder-card-example.svg', (True, 'placeholder')),
    ('/card-images/generic-token-creature.svg', (True, 'placeholder')),
    ('/card-images/absent.jpg', (False, 'missing')),
    ('https://cards.example/real.jpg', (False, 'remote')), (None, (False, 'missing'))])
def test_owned_image_presence_is_distinct_from_art_and_remote(tmp_path, uri, expected):
    media = tmp_path / 'media'
    media.mkdir()
    for name in ('real.jpg', 'placeholder-card-example.svg', 'generic-token-creature.svg'):
        (media / name).write_bytes(b'controlled public fixture')
    before = {p.name: (p.read_bytes(), p.stat().st_ino, p.stat().st_mtime_ns) for p in media.iterdir()}
    row = report(Rows([knowledge()], [cached(image=uri)]), image_cache_dir=media)['cards'][0]
    assert (field(row, 'local_image'), field(row, 'image_status')) == expected
    assert {p.name: (p.read_bytes(), p.stat().st_ino, p.stat().st_mtime_ns) for p in media.iterdir()} == before
    assert str(tmp_path) not in json.dumps(row)


@pytest.mark.parametrize('uri', ['/card-images/../outside', '/card-images/a/b',
    '/card-images/%2e%2e%2foutside', '/card-images/%72eal.jpg',
    '//evil.example/card-images/real.jpg', 'file:/card-images/real.jpg', '/other/real.jpg'])
def test_unsafe_or_encoded_image_paths_are_unavailable(tmp_path, uri):
    row = report(Rows([knowledge()], [cached(image=uri)]), image_cache_dir=tmp_path)['cards'][0]
    assert (field(row, 'local_image'), field(row, 'image_status')) == (None, 'unavailable')


@pytest.mark.parametrize('kind', ['leaf', 'root', 'directory'])
def test_symlink_and_nonregular_images_never_qualify(tmp_path, kind):
    media = tmp_path / 'media'
    media.mkdir()
    target = tmp_path / 'target'
    target.write_bytes(b'fixture, not an authorized image')
    if kind == 'leaf':
        (media / 'real.jpg').symlink_to(target)
    elif kind == 'root':
        alias = tmp_path / 'alias'
        alias.symlink_to(media, target_is_directory=True)
        media = alias
    else:
        (media / 'real.jpg').mkdir()
    row = report(Rows([knowledge()], [cached(image='/card-images/real.jpg')]), image_cache_dir=media)['cards'][0]
    assert (field(row, 'local_image'), field(row, 'image_status')) == (None, 'unavailable')


def test_probe_failure_and_missing_back_image_do_not_claim_front_coverage(tmp_path, monkeypatch):
    from card_data import placeholders
    (tmp_path / 'front.jpg').write_bytes(b'front')
    raw = knowledge('Front // Back')
    profile = json.loads(raw.profiles_json)
    profile['card_data']['card_faces'] = [{'name': 'Front', 'oracle_text': ''},
                                         {'name': 'Back', 'oracle_text': 'Flying'}]
    raw.profiles_json = json.dumps(profile)
    card = cached('Back', image='/card-images/front.jpg', faces=[
        {'name': 'Front', 'image_uri': '/card-images/front.jpg'},
        {'name': 'Back', 'image_uri': '/card-images/back.jpg'}])
    row = report(Rows([raw], [card]), ['Back'], image_cache_dir=tmp_path)['cards'][0]
    assert (field(row, 'local_image'), field(row, 'image_status')) == (False, 'missing')
    monkeypatch.setattr(placeholders, 'local_image_available', lambda *a, **k: (_ for _ in ()).throw(OSError('private path')))
    card.name = 'Diagnostic'
    row = report(Rows([knowledge()], [card]), image_cache_dir=tmp_path)['cards'][0]
    assert field(row, 'local_image') is None and field(row, 'image_status') == 'unavailable'
    assert 'private path' not in json.dumps(row)


def test_verified_variant_priority_and_requested_denominators_are_deterministic():
    rows = Rows([knowledge(rulings_verified='false'), knowledge(rulings_verified=True)])
    result = report(rows, ['Diagnostic', 'Missing', 'Diagnostic'])
    assert result == report(rows, ['Missing', 'Diagnostic'])
    assert result['requested_cards'] == 2
    assert result['cards'][0]['rulings_verified'] is True
    assert 'coverage' in result, 'Missing finite requested-card summary'
    assert result['coverage']['knowledge_present'] == 1
    assert result['coverage']['cached'] == 0
    assert result['coverage']['local_image_unavailable'] == 2
    assert result['rules_support_certified'] is False


def test_real_repository_report_preserves_rows_timestamps_and_media(tmp_path):
    from sqlalchemy.pool import StaticPool
    from sqlmodel import Session, SQLModel, create_engine
    from persistence.repository import Repository
    engine = create_engine('sqlite:///:memory:', poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            repo = Repository(session)
            repo.upsert_card({'name': 'Vanilla', 'scryfall_id': 'printing',
                              'oracle_text': '', 'image_uri': '/card-images/vanilla.svg'})
            repo.upsert_card_knowledge({'name': 'Vanilla', 'scryfall_id': 'printing',
                'oracle_source': 'scryfall', 'profiles': {'card_data': {
                    'name': 'Vanilla', 'oracle_id': 'oracle', 'oracle_text': ''},
                    'rulings_verified': True, 'rulings': []}})
            before = ([row.model_dump() for row in repo.list_cards()],
                      [row.model_dump() for row in repo.list_card_knowledge()])
            (tmp_path / 'vanilla.svg').write_bytes(b'public fixture')
            result = report(repo, ['Vanilla'], image_cache_dir=tmp_path)
            assert field(result['cards'][0], 'cached') is True
            assert field(result['cards'][0], 'local_image') is True
            assert field(result['cards'][0], 'oracle_text_blank') is True
            assert result['rulings_pending'] == []
            assert ([row.model_dump() for row in repo.list_cards()],
                    [row.model_dump() for row in repo.list_card_knowledge()]) == before
    finally:
        engine.dispose()
