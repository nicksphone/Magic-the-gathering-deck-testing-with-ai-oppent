"""Read-only import display facts are not engine execution certificates."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
from card_data.hydration import hydrate_deck_cards, ready_for_match
from card_data.sync import ScryfallSyncService
from decks.service import DeckService
from decks.builtin_decks import BUILTIN_DECKS
from tests.test_builtin_metadata_refresh import repo, seed_cache
from tests.generic_import_fixtures import client, parsed, FAMILIES


def dump(repo):
    return '\n'.join(repo.session.connection().connection.driver_connection.iterdump())


def time_warp():
    path = Path(__file__).parent / 'fixtures/queued_sequence/canonical.json'
    provenance = json.loads(path.with_name('provenance.json').read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == provenance['canonical_sha256']
    return json.loads(path.read_text())['Time Warp']


def forbid_sync(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Metadata projection must not sync, fetch, or materialize')
    for name in ('sync_card_by_name', 'sync_card_from_local_knowledge'):
        monkeypatch.setattr(ScryfallSyncService, name, forbidden)
    monkeypatch.setattr('card_data.sync.get_with_backoff', forbidden)


@pytest.mark.parametrize('name,style', FAMILIES)
@pytest.mark.parametrize('materialize', [False, True])
def test_seed_projection_readonly_printed_facts(repo, monkeypatch, name, style, materialize):
    forbid_sync(monkeypatch)
    board = parsed(repo, name).mainboard
    original = deepcopy(board)
    before = dump(repo)
    service = DeckService(repo)
    resolved = service._resolve_card_metadata(board, materialize=materialize)
    assert service._resolve_card_metadata(board, materialize=materialize) == resolved
    canonical = hydrate_deck_cards(repo, board)
    for item, facts in zip(resolved, canonical):
        meta = item['card_metadata']
        assert meta and meta['match_ready'] is True and 'id' not in meta
        assert meta['card_data_sources'] == ['offline_seed']
        for key in ('scryfall_id', 'mana_cost', 'type_line', 'oracle_text', 'colors'):
            assert meta.get(key) == facts.get(key)
    expected_curve = ({'lands':24,'1':16,'2':16,'3':4} if name == 'Burn'
                      else {'lands':28,'1':8,'2':15,'4':7,'5+':2})
    curve = service._compute_curve(resolved)
    assert all(curve[key] == expected_curve.get(key, 0) for key in curve)
    assert service._color_profile(resolved) == ({'W':4,'U':0,'B':0,'R':36,'G':0} if name == 'Burn'
                                                else {'W':0,'U':18,'B':18,'R':0,'G':0})
    assert board == original and dump(repo) == before
    assert repo.list_cards() == []


@pytest.mark.parametrize('stage', ['absent', 'manual', 'partial_cache', 'canonical'])
def test_unseeded_canonical_admission_no_materialization(repo, monkeypatch, stage):
    forbid_sync(monkeypatch)
    raw = time_warp()
    if stage in {'manual', 'canonical'}:
        repo.upsert_card_knowledge({'name':raw['name'], 'scryfall_id':raw['id'],
            'oracle_source':'scryfall' if stage == 'canonical' else 'manual',
            'profiles':{'schema_version':1, 'card_data':raw, 'rulings_verified':False, 'rulings':[]}})
    if stage == 'partial_cache':
        repo.upsert_card({'name':raw['name'], 'scryfall_id':raw['id'], 'type_line':raw['type_line'],
                          'mana_cost':raw['mana_cost'], 'oracle_text':'', 'colors':','.join(raw['colors'])})
    before = dump(repo)
    board = [{'card_name':raw['name'], 'quantity':4}]
    result = DeckService(repo)._resolve_card_metadata(board)[0]['card_metadata']
    assert DeckService(repo)._resolve_card_metadata(board, materialize=False)[0]['card_metadata'] == result
    if stage == 'canonical':
        assert result['match_ready'] is True and result['card_data_sources'] == ['local_knowledge']
        assert 'id' not in result and result['scryfall_id'] == raw['id']
        assert result['oracle_text'] == raw['oracle_text'] and result['rulings'] == []
    elif stage == 'partial_cache':
        assert result['match_ready'] is False and result['card_data_sources'] == ['cache']
        assert result['id'] == repo.get_cached_card_by_name(raw['name']).id
    else:
        assert result is None
    assert dump(repo) == before
    assert len(repo.list_cards()) == (1 if stage == 'partial_cache' else 0)


@pytest.mark.parametrize('name,style', FAMILIES)
def test_existing_cache_id_and_fields_priority(repo, monkeypatch, name, style):
    forbid_sync(monkeypatch)
    board = parsed(repo, name).mainboard
    seed_cache(repo, board)
    before = dump(repo)
    service = DeckService(repo)
    for item in service._resolve_card_metadata(board):
        card = repo.get_cached_card_by_name(item['card_name'])
        meta = item['card_metadata']
        for key, value in service._serialize_cached_card(card).items():
            assert meta[key] == value
        assert meta['id'] == card.id and meta['card_data_sources'] == ['cache']
        assert meta['match_ready'] == ready_for_match(meta)
    assert dump(repo) == before


@pytest.mark.parametrize('name,style', FAMILIES)
def test_http_import_seed_curve_colors_start_and_get_root(repo, client, monkeypatch, name, style):
    forbid_sync(monkeypatch)
    response = client.post('/decks/import', json={'name':name,'source':'user','deck_text':BUILTIN_DECKS[name]})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['archetype_guess'] == style and result['classification_status'] == 'resolved'
    assert result['mana_curve']['unknown'] == 0
    assert all(item['card_metadata']['match_ready'] for item in result['resolved_mainboard_cards'])
    assert repo.list_cards() == []
    assert client.get('/cards').json() == []
    started = client.post('/matches/start', json={'deck_a':result['mainboard'],'deck_b':result['mainboard'],
        'controller_a':'human','controller_b':'human','mode':'human_vs_human','seed':8128})
    assert started.status_code == 200, started.text
    import main
    monkeypatch.setattr(main, 'engine', repo.session.get_bind())
    match_id = started.json()['id']
    before = dump(repo)
    first = client.get(f'/matches/{match_id}').json()
    main.ACTIVE_MATCHES.clear()
    restored = client.get(f'/matches/{match_id}').json()
    assert first == restored and dump(repo) == before


@pytest.mark.parametrize('stage', ['absent', 'manual', 'partial_cache'])
def test_http_unadmitted_start_atomic(repo, client, monkeypatch, stage):
    test_unseeded_canonical_admission_no_materialization(repo, monkeypatch, stage)
    board = [{'card_name':'Time Warp','quantity':4},{'card_name':'Island','quantity':56}]
    before = dump(repo)
    response = client.post('/matches/start', json={'deck_a':board,'deck_b':board,
        'controller_a':'human','controller_b':'human','mode':'human_vs_human','seed':8128})
    assert response.status_code == 422, response.text
    assert response.json()['detail']['code'] == 'card_data_unavailable'
    assert dump(repo) == before
