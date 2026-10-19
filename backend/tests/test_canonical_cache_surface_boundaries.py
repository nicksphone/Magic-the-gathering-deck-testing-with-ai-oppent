"""Independent persistence, face framing, and corruption boundaries."""
from copy import deepcopy
import hashlib
import json

import pytest
from sqlalchemy.pool import NullPool
from sqlmodel import Session, create_engine

from card_data.hydration import hydrate_deck_cards, ready_for_match
from card_data.service import CardService
from card_data.sync import ScryfallSyncService
from persistence.repository import Repository
from game_state.state import MatchFactory
from rules_engine.colors import card_color_symbols
import tests.test_canonical_cache_surface_recovery as support


official = support.official
repo = support.repo


@pytest.mark.parametrize('entry', ['cached', 'sync_name'])
def test_repaired_selected_cache_persists_through_independent_engine(repo, official, entry):
    cards, rulings, _ = official
    raw = cards['Delver of Secrets // Insectile Aberration']
    row = support.store_knowledge(repo, raw, rulings[raw['id']])
    knowledge_before = row.model_dump()
    support.incomplete_cache(repo, raw, rulings[raw['id']], 'legacy_only')
    selected_before = repo.get_cached_card_by_name(raw['name']).model_dump()
    support.run_cached(repo, entry, raw['name'])
    original_connection = repo.session.connection().connection.driver_connection
    engine = create_engine(repo.session.bind.url, poolclass=NullPool)
    try:
        with Session(engine) as session:
            assert session.connection().connection.driver_connection is not original_connection
            reopened = Repository(session)
            selected = reopened.get_cached_card_by_name(raw['name'])
            expected = support.expected_payload(raw, rulings[raw['id']])
            assert selected.oracle_text == expected['oracle_text']
            assert selected.layout == raw['layout'] and len(json.loads(selected.card_faces_json)) == 2
            for key in ('id', 'name', 'scryfall_id', 'image_uri'):
                assert getattr(selected, key) == selected_before[key]
            assert reopened.get_card_knowledge(raw['name']).model_dump() == knowledge_before
            before_read = support.snapshot(reopened)
            listed = next(item for item in CardService(reopened).list_cards() if item['id'] == selected.id)
            serialized = ScryfallSyncService(reopened)._serialize_card(selected)
            for item in (listed, serialized):
                assert item['oracle_text'] == selected.oracle_text
                assert item['type_line'] == selected.type_line
                assert item['card_faces'] == json.loads(selected.card_faces_json)
            assert support.snapshot(reopened) == before_read
    finally:
        engine.dispose()


@pytest.mark.parametrize('entry', ['cached', 'sync_name'])
def test_back_face_display_cache_stays_valid_but_gameplay_uses_physical_front(repo, official, entry):
    cards, rulings, _ = official
    raw = cards['Delver of Secrets // Insectile Aberration']
    support.store_knowledge(repo, raw, rulings[raw['id']])
    back = raw['card_faces'][1]
    payload = support.expected_payload(raw, rulings[raw['id']])
    payload.update({key: back.get(key) for key in ('name', 'oracle_text', 'mana_cost', 'type_line', 'power', 'toughness')})
    payload['colors'] = ','.join(back.get('colors') or [])
    repo.upsert_card(payload)
    before = support.snapshot(repo)
    support.run_cached(repo, entry, back['name'])
    assert support.snapshot(repo) == before
    hydrated = hydrate_deck_cards(repo, [{'quantity': 1, 'card_name': back['name']}])[0]
    front = raw['card_faces'][0]
    assert hydrated['oracle_text'] == front['oracle_text']
    assert hydrated['type_line'] == front['type_line']
    assert hydrated['power'] == front['power'] and hydrated['toughness'] == front['toughness']
    assert [face['name'] for face in hydrated['card_faces']] == [face['name'] for face in raw['card_faces']]
    assert support.snapshot(repo) == before


def test_rule_repair_orders_all_faces_and_preserves_art_and_unknown_keys_by_name(repo, official):
    cards, rulings, _ = official
    raw = cards['Delver of Secrets // Insectile Aberration']
    support.store_knowledge(repo, raw, rulings[raw['id']])
    payload = support.expected_payload(raw, rulings[raw['id']])
    faces = list(reversed(json.loads(payload['card_faces_json'])))
    protected = {}
    for index, face in enumerate(faces):
        face['image_uri'] = 'https://example.invalid/retained-face-' + str(index)
        face['future_extension'] = {'opaque': [index, {'keep': True}]}
        protected[face['name']] = deepcopy({key: face[key] for key in ('image_uri', 'future_extension')})
    payload.update(oracle_text='', type_line='Creature', layout='', card_faces_json=json.dumps(faces))
    repo.upsert_card(payload)
    before_knowledge = support.snapshot(repo)[0]
    support.run_cached(repo, 'cached', raw['name'])
    selected = repo.get_cached_card_by_name(raw['name'])
    assert selected.oracle_text == support.expected_payload(raw, rulings[raw['id']])['oracle_text']
    repaired = json.loads(selected.card_faces_json)
    assert [face['name'] for face in repaired] == [face['name'] for face in raw['card_faces']]
    assert {face['name']: {key: face[key] for key in ('image_uri', 'future_extension')}
            for face in repaired} == protected
    assert support.snapshot(repo)[0] == before_knowledge
    before = support.snapshot(repo)
    support.run_cached(repo, 'cached', raw['name'])
    assert support.snapshot(repo) == before


@pytest.mark.parametrize('corruption', ['object_not_faces', 'typed_oracle'])
def test_hydration_rejects_typed_cache_corruption_before_canonical_overlay(repo, official, corruption):
    cards, rulings, _ = official
    raw = cards['Delver of Secrets // Insectile Aberration']
    support.store_knowledge(repo, raw, rulings[raw['id']])
    payload = support.expected_payload(raw, rulings[raw['id']])
    payload['card_faces_json'] = json.dumps({} if corruption == 'object_not_faces' else [
        {'name': raw['card_faces'][0]['name'], 'oracle_text': 17}])
    repo.upsert_card(payload)
    before = support.snapshot(repo)
    metadata = hydrate_deck_cards(repo, [{'quantity': 1, 'card_name': raw['name']}])[0]
    assert metadata['type_line'] == '' and metadata['card_faces'] == []
    assert metadata['card_data_sources'] == []
    assert support.snapshot(repo) == before


def test_hydration_pending_rulings_still_uses_valid_local_canonical_facts(repo, official):
    cards, rulings, _ = official
    raw = cards['Delver of Secrets // Insectile Aberration']
    row = support.store_knowledge(repo, raw, rulings[raw['id']])
    profile = json.loads(row.profiles_json)
    profile['rulings_verified'] = False
    row.profiles_json = json.dumps(profile)
    repo.session.add(row)
    repo.session.commit()
    before = support.snapshot(repo)
    support.assert_hydrated_front(repo, raw)
    assert support.snapshot(repo) == before


@pytest.mark.parametrize('corruption', ['scalar_colors', 'duplicate_name', 'unknown_name'])
def test_malformed_face_rules_fail_closed_without_read_exceptions_or_repair(repo, official, corruption):
    cards, rulings, _ = official
    raw = cards['Delver of Secrets // Insectile Aberration']
    support.store_knowledge(repo, raw, rulings[raw['id']])
    payload = support.expected_payload(raw, rulings[raw['id']])
    faces = json.loads(payload['card_faces_json'])
    # Deliberate malformed protocol records, never asserted as canonical facts.
    if corruption == 'scalar_colors':
        faces[0]['colors'] = 'U'
    elif corruption == 'duplicate_name':
        faces[1]['name'] = faces[0]['name']
    else:
        faces[0]['name'] = 'Noncanonical protocol face'
    payload['card_faces_json'] = json.dumps(faces)
    repo.upsert_card(payload)
    before = support.snapshot(repo)
    metadata = hydrate_deck_cards(repo, [{'quantity': 1, 'card_name': raw['name']}])[0]
    assert not ready_for_match(metadata)
    assert metadata['type_line'] == '' and metadata['card_faces'] == []
    assert metadata['card_data_sources'] == []
    assert ScryfallSyncService(repo).sync_card_from_local_knowledge(raw['name']) is False
    assert support.snapshot(repo) == before


@pytest.mark.parametrize('entry', ['cached', 'sync_name'])
def test_canonical_single_face_with_legacy_null_faces_is_not_refreshed(repo, official, entry):
    cards, rulings, _ = official
    raw = cards['Lightning Bolt']
    support.store_knowledge(repo, raw, rulings[raw['id']])
    payload = support.expected_payload(raw, rulings[raw['id']])
    payload['card_faces_json'] = 'null'
    repo.upsert_card(payload)
    before = support.snapshot(repo)
    support.run_cached(repo, entry, raw['name'])
    metadata = hydrate_deck_cards(repo, [{'quantity': 1, 'card_name': raw['name']}])[0]
    assert ready_for_match(metadata)
    assert metadata['oracle_text'] == raw['oracle_text'] and metadata['card_faces'] == []
    assert support.snapshot(repo) == before


@pytest.mark.parametrize('name,expected_colors', [
    ('Bonecrusher Giant // Stomp', {'R'}),
    ('Brutal Cathar // Moonrage Brute', {'W'}),
])
def test_physical_front_keeps_absent_versus_explicit_face_colors(repo, official, name, expected_colors):
    cards, rulings, _ = official
    raw = cards[name]
    support.store_knowledge(repo, raw, rulings[raw['id']])
    repo.upsert_card(support.expected_payload(raw, rulings[raw['id']]))
    before = support.snapshot(repo)
    metadata = hydrate_deck_cards(repo, [{'quantity': 1, 'card_name': name}])[0]
    assert set(metadata['colors']) == expected_colors
    state = MatchFactory.from_decks([metadata], [metadata], seed=4)
    assert all(card_color_symbols(card) == expected_colors for card in state.cards.values())
    assert support.snapshot(repo) == before


@pytest.mark.parametrize('entry', ['cached', 'sync_name'])
@pytest.mark.parametrize('face_name', ['Commit', 'Memory'])
def test_complete_split_display_alias_does_not_refresh_rule_fields(repo, entry, face_name):
    directory = support.FIXTURES / 'spell_admission_safety'
    data = (directory / 'canonical.json').read_bytes()
    proof = json.loads((directory / 'provenance.json').read_text())
    pin = 'a789129a43548da1bc0821b0c6cf52e88487f8f744dacb12e644861546fef923'
    assert hashlib.sha256(data).hexdigest() == proof['canonical_sha256'] == pin
    raw = json.loads(data)['Commit // Memory']
    assert hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == (
        proof['rows'][raw['name']]['raw_sha256']) == '51c42d90bb5e44c48e32cd59420e429339235190b11b5fead0214ee2d6f6fb74'
    # Verified flag/empty rulings are protocol inputs, not an archived rulings claim.
    support.store_knowledge(repo, raw, [])
    payload = support.expected_payload(raw, [])
    face = next(face for face in raw['card_faces'] if face['name'] == face_name)
    payload.update({key: face.get(key) for key in ('name', 'oracle_text', 'mana_cost', 'type_line', 'power', 'toughness')})
    if face.get('colors') is not None:
        payload['colors'] = ','.join(face['colors'])
    repo.upsert_card(payload)
    before = support.snapshot(repo)
    support.run_cached(repo, entry, face_name)
    assert support.snapshot(repo) == before
