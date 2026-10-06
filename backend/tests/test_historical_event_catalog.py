"""Historical import contracts on synthetic local SQLite, not rules certification."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import pickle

import pytest

from card_data.fallback_cards import fallback_card_payload
from card_data.sync import ScryfallSyncService
from card_data.hydration import hydrate_deck_cards
from decks import bootstrap
from decks.catalog import CatalogFacts, DATA_PATH, DATA_SHA256, catalog_context, event_record, load_catalog
from decks.expansion_top_decks import EXPANSION_TOP_DECKS, EXPANSION_TOP_DECKS_BY_CODE
from decks.service import DeckService
from tests.test_builtin_metadata_refresh import repo, rows
from tests.generic_import_fixtures import client
from game_state.state import MatchFactory
from game_state.serializers import serialize_match_snapshot

FIXTURE = Path(__file__).parent / 'fixtures' / 'historical_event_catalog'
RAW = {r['id']: r for r in map(json.loads, (FIXTURE / 'canonical.jsonl').read_text().splitlines())}
TRACE = []


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError('Catalog import must not fetch external card metadata')
    monkeypatch.setattr(socket.socket, 'connect', reject)


def sql_dump(repo):
    return list(repo.session.connection().connection.driver_connection.iterdump())


def test_full_verified_catalog_facts_and_original52_preservation():
    packet = load_catalog()
    assert packet['cards'] == RAW
    assert hashlib.sha256(DATA_PATH.read_bytes()).hexdigest() == DATA_SHA256
    old = json.loads((FIXTURE / 'inventory52.json').read_text())['rows']
    assert [r['code'] for r in EXPANSION_TOP_DECKS[:52]] == [r['code'] for r in old]
    assert len(EXPANSION_TOP_DECKS) == 53 and EXPANSION_TOP_DECKS[-1]['code'] == 'MH3'
    for prior, actual in zip(old, EXPANSION_TOP_DECKS, strict=False):
        assert hashlib.sha256(actual['deck_text'].encode()).hexdigest() == prior['deck_text_sha256']
        for key in prior:
            if key not in actual or key in {'decklist_source_url', 'event_source_url'} and prior['code'] == 'OTJ':
                continue
            assert actual[key] == prior[key]
    assert sum(r['kind'] == 'archetype_template' for r in EXPANSION_TOP_DECKS) == 51
    assert sum(r['kind'] == 'tournament' for r in EXPANSION_TOP_DECKS) == 2


@pytest.mark.parametrize('code', ['OTJ', 'MH3'])
def test_actual_HTTP_cold_import_all75_joined_without_card_cache_writes(repo, client, code):
    item = EXPANSION_TOP_DECKS_BY_CODE[code]
    before_cache = [r.model_dump(mode='json') for r in repo.list_cards()]
    response = client.post(f'/decks/expansion-top/{code}/import')
    assert response.status_code == 200
    out = response.json()
    assert out['errors'] == out['suggestions'] == []
    assert sum(r['quantity'] for r in out['mainboard']) == 60
    assert sum(r['quantity'] for r in out['sideboard']) == 15
    projected = out['resolved_mainboard_cards'] + out['resolved_sideboard_cards']
    assert sum(r['quantity'] for r in projected if r['card_metadata']) == 75
    expected = event_record(code)
    for section in ['mainboard', 'sideboard']:
        actual = out['resolved_' + section + '_cards']
        by_name = {r['canonical_name']: r for r in expected[section]}
        assert len(actual) == len(by_name)
        assert {r['card_metadata']['name'] for r in actual} == set(by_name)
        for row in actual:
            metadata = row['card_metadata']
            original = by_name[metadata['name']]
            assert row['quantity'] == original['quantity']
            seed = fallback_card_payload(original['canonical_name'])
            admitted_id = seed['scryfall_id'] if seed else original['scryfall_id']
            assert metadata['scryfall_id'] == admitted_id
            assert metadata['name'] == original['canonical_name']
            assert metadata['match_ready'] is True  # Existing metadata predicate only.
    saved = next(r for r in repo.list_decks() if r.id == out['deck_id'])
    assert saved.source == 'expansion_top:' + code.lower() and saved.name == item['deck_name']
    assert json.loads(saved.mainboard_json) == out['mainboard']
    assert json.loads(saved.sideboard_json) == out['sideboard']
    assert out['catalog']['format_context']['scope'] == 'historical_event'
    assert out['catalog']['format_context']['current_format_admission'] == 'unsupported'
    assert out['catalog']['runtime_effect_certificate'] is False
    assert out['catalog']['constructed_best_claim'] is False
    assert [r.model_dump(mode='json') for r in repo.list_cards()] == before_cache
    assert repo.list_card_knowledge_names() == []
    TRACE.append({'kind': 'HTTP-cold75', 'code': code, 'response': out})


@pytest.mark.parametrize('code', ['OTJ', 'MH3'])
@pytest.mark.parametrize('source_form', ['upper', 'whitespace'])
def test_import_reuses_latest_exact_source_preserves_user_history_ids_inventory(repo, client, code, source_form):
    service = DeckService(repo)
    first = service.import_expansion_top_deck(code)
    item = EXPANSION_TOP_DECKS_BY_CODE[code]
    user = repo.save_deck(item['deck_name'], 'user', first['mainboard'], first['sideboard'], 'unknown')
    source = ('EXPANSION_TOP:' + code) if source_form == 'upper' else (' expansion_top:' + code.lower() + ' ')
    latest = repo.save_deck(item['deck_name'], source, first['mainboard'], first['sideboard'], first['archetype_guess'])
    before = rows(repo)
    for _ in range(2):
        response = client.post(f'/decks/expansion-top/{code}/import', json={'format_scope': 'historical'})
        assert response.status_code == 200 and response.json()['deck_id'] == latest.id
        after = rows(repo)
        assert after == before
        assert after[user.id] == before[user.id] and after[first['deck_id']] == before[first['deck_id']]
    TRACE.append({'kind': 'source-ID-history', 'code': code, 'source': source,
                  'latest_id': latest.id, 'history_id': first['deck_id'], 'user_id': user.id,
                  'all_row_fields_equal': True})


@pytest.mark.parametrize('path', ['OTJ/import', 'MH3/import', 'LEA/import', 'import-all'])
@pytest.mark.parametrize('intent', ['body', 'query', 'both'])
def test_current_format_requests_reject_before_persistence_full_SQL_unchanged(repo, client, path, intent):
    preserved = DeckService(repo).import_expansion_top_deck('OTJ')
    state = MatchFactory.from_decks(
        hydrate_deck_cards(repo, [{'quantity': 60, 'card_name': 'Island'}]),
        hydrate_deck_cards(repo, [{'quantity': 60, 'card_name': 'Forest'}]), seed=85)
    root_before = pickle.dumps(state)
    repo.save_active_match(state.id, json.dumps(serialize_match_snapshot(state)),
                           json.dumps({'1': 'human', '2': 'human'}))
    before = sql_dump(repo)
    query = '?format_scope=current' if intent in {'query', 'both'} else ''
    body = {'format_scope': 'current'} if intent == 'body' else {'format_scope': 'historical'}
    response = client.post('/decks/expansion-top/' + path + query, json=body)
    assert response.status_code == 422
    assert response.json()['detail']['code'] == 'current_catalog_format_unsupported'
    assert sql_dump(repo) == before
    assert pickle.dumps(state) == root_before
    assert any(r.id == preserved['deck_id'] for r in repo.list_decks())


@pytest.mark.parametrize('body', [{'format_scope': 'future'}, {'format': 'Modern'},
                                  {'current_legality': 'legal'}, {'runtime_effect_certificate': True}])
def test_unknown_format_or_certification_intents_are_strict_4xx_and_atomic(repo, client, body):
    before = sql_dump(repo)
    response = client.post('/decks/expansion-top/MH3/import', json=body)
    assert response.status_code == 422 and sql_dump(repo) == before


def test_template_and_tournament_HTTP_context_and_helper_parity(repo, client):
    expected = DeckService(repo).list_expansion_top_decks()
    assert client.get('/decks/expansion-top').json() == expected
    for code in ['OTJ', 'MH3', 'LEA']:
        item = EXPANSION_TOP_DECKS_BY_CODE[code]
        response = client.get('/decks/expansion-top/' + code)
        assert response.status_code == 200
        assert response.json()['catalog'] == catalog_context(item)
        context = response.json()['catalog']
        if item['kind'] == 'archetype_template':
            assert context['format_context']['format_name'] is None
            assert context['finish_scope'] is None and context['provenance'] is None
        else:
            assert context['format_context']['event_start_date'].startswith('2024-')
            assert context['finish_scope'] == 'overall_event'
        assert context['format_context']['current_format_admission'] == 'unsupported'


def test_existing_Adventure_seed_faces_remain_priority_with_bounded_canonical_seed_append(repo):
    seed = deepcopy(fallback_card_payload("Imodane's Recruiter"))
    service = DeckService(CatalogFacts(repo, EXPANSION_TOP_DECKS_BY_CODE['OTJ']))
    out = service.import_deck_text('Seed priority', EXPANSION_TOP_DECKS_BY_CODE['OTJ']['deck_text'])
    metadata = next(r['card_metadata'] for r in out['resolved_mainboard_cards']
                    if r['card_metadata']['name'].startswith("Imodane's Recruiter"))
    assert [f['colors'] for f in metadata['card_faces']] == [['R'], ['W']]
    assert 'offline_seed' in metadata['card_data_sources']
    assert fallback_card_payload("Imodane's Recruiter") == seed
    canonical = next(r for r in RAW.values() if r['name'] == 'Nadu, Winged Wisdom')
    assert fallback_card_payload('Nadu, Winged Wisdom') == {**canonical, 'scryfall_id': canonical['id']}
    assert catalog_context(EXPANSION_TOP_DECKS_BY_CODE['MH3'])['offline_facts']['global_match_hydration_certified'] is False


def test_cache_priority_with_genuine_card_no_fact_materialization(repo):
    raw = next(r for r in RAW.values() if r['name'] == 'The One Ring')
    packet = ScryfallSyncService._normalize_payload(raw, ScryfallSyncService._extract_remote_image_uri(raw))
    repo.upsert_card(packet)
    before = [r.model_dump(mode='json') for r in repo.list_cards()]
    out = DeckService(repo).import_expansion_top_deck('MH3')
    metadata = next(r['card_metadata'] for r in out['resolved_mainboard_cards'] if r['card_name'] == 'The One Ring')
    assert metadata['card_data_sources'] == ['cache']
    assert metadata['scryfall_id'] == raw['id']
    assert [r.model_dump(mode='json') for r in repo.list_cards()] == before


def test_all_original52_saved_ids_inventory_and_append_only_startup(repo):
    service = DeckService(repo)
    for item in EXPANSION_TOP_DECKS[:52]:
        imported = service.import_expansion_top_deck(item['code'])
        assert imported['errors'] == []
    before = rows(repo)
    assert len(before) == 52
    bootstrap.ensure_expansion_top_decks(repo)
    after = rows(repo)
    assert all(after[rid] == row for rid, row in before.items())
    assert len(after) == 53
    mh3 = next(r for r in repo.list_decks() if r.source == 'expansion_top:mh3')
    assert mh3.id == 53 and sum(r['quantity'] for r in json.loads(mh3.sideboard_json)) == 15
    bootstrap.ensure_expansion_top_decks(repo)
    assert rows(repo) == after


def test_mutated_catalog_packet_refuses_to_claim_provenance(tmp_path):
    path = tmp_path / 'damaged-catalog.json'
    packet = json.loads(DATA_PATH.read_text())
    packet['events']['MH3']['runtime_effect_certificate'] = True
    path.write_text(json.dumps(packet))
    with pytest.raises(ValueError, match='digest mismatch'):
        load_catalog(path)
