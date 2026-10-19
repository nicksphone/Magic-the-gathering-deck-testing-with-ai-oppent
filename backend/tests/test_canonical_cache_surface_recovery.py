"""Full archived facts versus explicitly synthetic incomplete legacy cache rows."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from card_data import placeholders, sync
from card_data.hydration import hydrate_deck_cards
from card_data.tactical import canonical_tactical_tags
from knowledge.ingest import KnowledgeIngestor, SCHEMA_VERSION
from knowledge.models import CardKnowledge
from persistence.models import CardCache
from persistence.repository import Repository


FIXTURES = Path(__file__).parent / 'fixtures'
IMAGE = 'https://example.invalid/offline-fixture-art.png'


@pytest.fixture(scope='module')
def official():
    root = FIXTURES / 'knowledge_profiles'
    raw = (root / 'seed155-scryfall.jsonl').read_bytes()
    pages = (root / 'seed155-rulings.jsonl').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
    assert hashlib.sha256(pages).hexdigest() == 'f54b2bae40fffe3e1714877851bf65cbb854b551951d09cc20f7cadfb70994f9'
    provenance = json.loads((root / 'PROVENANCE.json').read_bytes())
    assert provenance['snapshot_sha256'] == hashlib.sha256(raw).hexdigest()
    assert provenance['oracle_modified'] is False
    cards = {row['name']: row for row in map(json.loads, raw.splitlines())}
    rulings = {page['card_id']: page['payload']['data']
               for page in map(json.loads, pages.splitlines())}
    alternate = (FIXTURES / 'empty_hand_attack_witness' / 'island.json').read_bytes()
    pin = 'd8d45bda942640f4cbcc5af201e1a91e13785fa7f266303af031531b11782c43'
    assert hashlib.sha256(alternate).hexdigest() == pin
    receipt = json.loads((FIXTURES / 'empty_hand_attack_witness' / 'provenance.json').read_bytes())
    record = next(row for row in receipt['cards'] if row['file'] == 'island.json')
    assert record['sha256'] == pin and record['full_raw_response'] is True
    alternate = json.loads(alternate)
    assert alternate['oracle_id'] == record['oracle_id'] == cards['Island']['oracle_id']
    assert alternate['id'] != cards['Island']['id']
    return cards, rulings, alternate


@pytest.fixture
def repo(tmp_path, monkeypatch):
    media = tmp_path / 'media'
    media.mkdir()
    monkeypatch.setattr(sync, 'CACHE_DIR', media)
    monkeypatch.setattr(placeholders, 'CACHE_DIR', media)
    engine = create_engine('sqlite:///' + str(tmp_path / 'owned.sqlite'), poolclass=StaticPool)
    SQLModel.metadata.create_all(engine, tables=[CardKnowledge.__table__, CardCache.__table__])
    try:
        with Session(engine) as session:
            yield Repository(session)
    finally:
        engine.dispose()


@pytest.fixture(scope='module')
def blank_vanilla():
    root = Path(__file__).parent / 'vraska_full' / 'fixtures'
    raw = (root / 'grizzly-bears-scryfall-raw.json').read_bytes()
    pin = '150049326ad0c3b914719c54709331b3a51d11a18c02dde60c64246f3ac8239c'
    assert hashlib.sha256(raw).hexdigest() == pin
    provenance = json.loads((root / 'PROVENANCE.json').read_bytes())
    assert provenance['fixture_bytes']['grizzly-bears-scryfall-raw.json'] == pin
    card = json.loads(raw)
    assert card['object'] == 'card' and card['oracle_text'] == ''
    return card


def store_knowledge(repo, raw, rulings):
    # Deliberately valid legacy metadata: the optional per-row hash is absent.
    profile = {
        'schema_version': SCHEMA_VERSION,
        'oracle_id': raw['oracle_id'],
        'card_data': deepcopy(raw),
        'rulings_verified': True,
        'rulings': deepcopy(rulings),
        'learned_extension': {'nested': {'opaque': ['preserve', 23]}},
        'future_namespace': {'faces': [{'unknown': {'retain': True}}]},
        **canonical_tactical_tags(raw),
    }
    return repo.upsert_card_knowledge({
        'name': raw['name'], 'scryfall_id': raw['id'], 'oracle_source': 'scryfall',
        'play_value': 7.25, 'threat_level': 2, 'etb_impact': 1.5,
        'answerable_by': ['counter'], 'cast_windows': ['instant_window'],
        'profiles': profile,
    })


def expected_payload(raw, rulings):
    image = sync.ScryfallSyncService._extract_remote_image_uri(raw)
    assert image
    return sync.ScryfallSyncService._normalize_payload(raw, image, rulings)


def incomplete_cache(repo, raw, rulings, topology):
    expected = expected_payload(raw, rulings)
    # These are noncanonical legacy-protocol mutations, NOT altered official RAW.
    incomplete = {**expected, 'oracle_text': '', 'type_line': 'Creature',
                  'layout': '', 'card_faces_json': '[]', 'image_uri': IMAGE}
    if topology != 'legacy_only':
        repo.upsert_card(incomplete)
    if topology != 'canonical_incomplete':
        repo.upsert_card({**incomplete, 'scryfall_id': 'legacy-placeholder:not-a-canonical-printing'})
    selected = repo.get_cached_card_by_name(raw['name'])
    assert selected.oracle_text == '' and selected.layout == '' and selected.card_faces_json == '[]'
    if topology == 'duplicate_exact':
        rows = repo.session.exec(select(CardCache).where(CardCache.name == raw['name'])).all()
        assert len(rows) == 2
        assert selected.scryfall_id == 'legacy-placeholder:not-a-canonical-printing'


def snapshot(repo):
    return ([row.model_dump() for row in repo.list_card_knowledge()],
            [row.model_dump() for row in repo.list_cards()])


def run_cached(repo, entry, name):
    requests = []
    def offline(request):
        requests.append(request.url.path)
        pytest.fail('Canonical cache recovery must not make an HTTP request')
    with httpx.Client(transport=httpx.MockTransport(offline)) as client:
        result = getattr(KnowledgeIngestor(repo, client), entry)(name)
    assert requests == []
    return result


def assert_hydrated_front(repo, raw):
    hydrated = hydrate_deck_cards(repo, [{'quantity': 1, 'card_name': raw['name']}])[0]
    front = raw['card_faces'][0]
    assert hydrated['layout'] == raw['layout']
    assert len(hydrated['card_faces']) == len(raw['card_faces'])
    assert hydrated['oracle_text'] == front['oracle_text']
    assert hydrated['type_line'] == front['type_line']
    assert hydrated['mana_cost'] == front['mana_cost']
    return hydrated


@pytest.mark.parametrize('entry', ['cached', 'sync_name'])
@pytest.mark.parametrize('topology', ['legacy_only', 'canonical_incomplete', 'duplicate_exact'])
def test_cached_entry_repairs_incomplete_transform_offline_and_is_idempotent(repo, official, entry, topology):
    cards, rulings, _ = official
    raw = cards['Delver of Secrets // Insectile Aberration']
    row = store_knowledge(repo, raw, rulings[raw['id']])
    knowledge_before = row.model_dump()
    incomplete_cache(repo, raw, rulings[raw['id']], topology)
    selected_before = repo.get_cached_card_by_name(raw['name']).model_dump()
    cache_before = {card.id: card.model_dump() for card in repo.list_cards()}
    result = run_cached(repo, entry, raw['name'])
    assert result == 'cached' if entry == 'sync_name' else result.id == row.id
    assert repo.get_card_knowledge(raw['name']).model_dump() == knowledge_before
    selected = repo.get_cached_card_by_name(raw['name'])
    assert selected.id == selected_before['id']
    expected = expected_payload(raw, rulings[raw['id']])
    rules = {'oracle_text', 'mana_cost', 'type_line', 'layout', 'colors',
             'power', 'toughness', 'loyalty', 'card_faces_json'}
    assert {key: getattr(selected, key) for key in rules} == {key: expected[key] for key in rules}
    protected = set(selected_before) - rules - {'updated_at'}
    assert {key: getattr(selected, key) for key in protected} == {
        key: selected_before[key] for key in protected}
    assert {card.id: card.model_dump() for card in repo.list_cards() if card.id != selected.id} == {
        key: value for key, value in cache_before.items() if key != selected.id}
    assert_hydrated_front(repo, raw)
    stable = snapshot(repo)
    run_cached(repo, entry, raw['name'])
    assert snapshot(repo) == stable
    with Session(repo.session.bind) as session:
        assert Repository(session).get_card_knowledge(raw['name']).model_dump() == knowledge_before


@pytest.mark.parametrize('topology', ['legacy_only', 'canonical_incomplete', 'duplicate_exact'])
def test_hydration_canonical_transform_fields_survive_incomplete_cache(repo, official, topology):
    cards, rulings, _ = official
    raw = cards['Delver of Secrets // Insectile Aberration']
    store_knowledge(repo, raw, rulings[raw['id']])
    incomplete_cache(repo, raw, rulings[raw['id']], topology)
    before = snapshot(repo)
    try:
        assert_hydrated_front(repo, raw)
    finally:
        assert snapshot(repo) == before, 'Read-only hydration mutated stored knowledge or cache'


@pytest.mark.parametrize('entry', ['cached', 'sync_name'])
def test_genuine_different_printing_with_same_rules_is_not_refreshed(repo, official, entry):
    cards, rulings, alternate = official
    raw = cards['Island']
    store_knowledge(repo, raw, rulings[raw['id']])
    repo.upsert_card(expected_payload(alternate, rulings[raw['id']]))
    before = snapshot(repo)
    run_cached(repo, entry, raw['name'])
    assert snapshot(repo) == before
    assert repo.get_cached_card_by_name(raw['name']).scryfall_id == alternate['id']
    assert raw['oracle_text'] == alternate['oracle_text']


@pytest.mark.parametrize('entry', ['cached', 'sync_name'])
def test_genuine_empty_oracle_vanilla_is_not_missing_facts(repo, blank_vanilla, entry):
    raw = blank_vanilla
    # Empty rulings/verified marker here are unit protocol inputs, not a claim
    # that an upstream Grizzly Bears rulings response was captured in seed155.
    store_knowledge(repo, raw, [])
    repo.upsert_card(expected_payload(raw, []))
    before = snapshot(repo)
    run_cached(repo, entry, raw['name'])
    assert snapshot(repo) == before
    metadata = hydrate_deck_cards(repo, [{'quantity': 1, 'card_name': raw['name']}])[0]
    assert metadata['oracle_text'] == '' and metadata['type_line'] == raw['type_line']


@pytest.mark.parametrize('entry', ['cached', 'sync_name'])
def test_genuine_front_face_alias_remains_accepted_without_refresh(repo, official, entry):
    cards, rulings, _ = official
    raw = cards['Delver of Secrets // Insectile Aberration']
    store_knowledge(repo, raw, rulings[raw['id']])
    front = raw['card_faces'][0]
    payload = expected_payload(raw, rulings[raw['id']])
    # A cache display-name alias uses genuine face fields, never fabricated Oracle.
    payload.update({key: front.get(key) for key in ('name', 'oracle_text', 'mana_cost', 'type_line', 'power', 'toughness')})
    repo.upsert_card(payload)
    before = snapshot(repo)
    run_cached(repo, entry, front['name'])
    assert snapshot(repo) == before
    hydrated = hydrate_deck_cards(repo, [{'quantity': 1, 'card_name': front['name']}])[0]
    assert hydrated['oracle_text'] == front['oracle_text'] and hydrated['type_line'] == front['type_line']


def test_complete_transform_without_optional_legacy_hash_is_already_cached(repo, official):
    cards, rulings, _ = official
    raw = cards['Delver of Secrets // Insectile Aberration']
    row = store_knowledge(repo, raw, rulings[raw['id']])
    assert 'card_data_sha256' not in json.loads(row.profiles_json)
    repo.upsert_card(expected_payload(raw, rulings[raw['id']]))
    before = snapshot(repo)
    run_cached(repo, 'sync_name', raw['name'])
    assert_hydrated_front(repo, raw)
    assert snapshot(repo) == before
