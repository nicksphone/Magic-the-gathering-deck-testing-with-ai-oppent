"""Desired official-source identity and bounded sideboard admission contracts."""
from copy import deepcopy
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import pickle
import subprocess
import sys

import pytest
from decks.service import DeckService
from tests.test_builtin_metadata_refresh import repo
from tests.generic_import_fixtures import client
from tests.import_identity_fix_support import FAMILIES, assert_provenance, cards, prepare, rows


@pytest.mark.parametrize('code,front,expected', FAMILIES)
@pytest.mark.parametrize('mode', ['offline', 'missing'])
@pytest.mark.parametrize('latest_source', ['lower', 'upper', 'mixed', 'whitespace'])
@pytest.mark.parametrize('existing', [False, True])
def test_official_latest_normalized_source_reuses_exact_id_history(repo, client, monkeypatch, code, front, expected, mode, latest_source, existing):
    item = prepare(repo, monkeypatch, code, front, mode)
    p = DeckService(repo).parser.parse(item['deck_text'])
    selected = None
    if existing:
        sources = ['expansion_top:'+code.lower(), 'EXPANSION_TOP:'+code,
                   'Expansion_Top:'+code.lower(), ' expansion_top:'+code.lower()+' ']
        for i, source in enumerate(sources):
            row = repo.save_deck(item['deck_name'], source, p.mainboard, p.sideboard, 'historical')
            row.created_at = datetime(2020, 1, 1) + timedelta(days=i)
            if i == ['lower', 'upper', 'mixed', 'whitespace'].index(latest_source):
                selected = row
                row.created_at = datetime(2021, 1, 1)
        repo.session.commit()
    user = repo.save_deck(item['deck_name'], 'user', p.mainboard, p.sideboard, 'historical')
    custom = repo.save_deck(item['deck_name'], 'expansion_top:'+code+'-custom', p.mainboard, p.sideboard, 'historical')
    before, before_cards = rows(repo), cards(repo)
    results = []
    for submitted in (code.lower(), code):
        response = client.post('/decks/expansion-top/'+submitted+'/import')
        assert response.status_code == 200, response.text
        result = response.json()
        assert not result['errors'] and assert_provenance(repo, result) == (mode == 'offline')
        assert result['archetype_guess'] == (expected if mode == 'offline' else 'unknown')
        results.append(result)
    rid = str(results[0]['deck_id'])
    assert results[0]['deck_id'] == results[1]['deck_id']
    after = rows(repo)
    if existing:
        assert rid == str(selected.id) and set(after) == set(before)
        assert after[rid]['source'] == before[rid]['source']
        assert after[rid]['created_at'] == before[rid]['created_at']
    else:
        assert set(after) == set(before) | {rid}
        assert after[rid]['source'] == 'expansion_top:'+code.lower()
    assert all(after[key] == value for key, value in before.items() if key != rid)
    assert str(user.id) in after and str(custom.id) in after and cards(repo) == before_cards


@pytest.mark.parametrize('code,front,expected', FAMILIES)
@pytest.mark.parametrize('mode', ['offline', 'missing'])
@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('count', [15, 16])
def test_sideboard_boundary_http_before_persistence(repo, client, monkeypatch, code, front, expected, mode, existing, count):
    item = prepare(repo, monkeypatch, code, front, mode)
    p = DeckService(repo).parser.parse(item['deck_text'])
    source = 'expansion_top:'+code.lower()
    if existing:
        repo.save_deck(item['deck_name'], source, p.mainboard, p.sideboard, 'historical')
    before, before_cards = rows(repo), cards(repo)
    text = item['deck_text'].split('Sideboard:')[0]+'\nSideboard:\n'+str(count-1)+' Mountain\n1 Mountain'
    response = client.post('/decks/import', json={'name':item['deck_name'], 'source':source, 'deck_text':text})
    if count == 16:
        assert response.status_code == 422, response.text
        assert response.json()['detail'] == {'code':'sideboard_limit_exceeded', 'maximum':15, 'actual':16}
        assert rows(repo) == before and cards(repo) == before_cards
    else:
        assert response.status_code == 200 and not response.json()['errors']
        result = response.json()
        assert sum(c['quantity'] for c in result['sideboard']) == 15
        assert assert_provenance(repo, result) == (mode == 'offline')
        assert set(rows(repo)) == (set(before) if existing else set(before)|{str(result['deck_id'])})


@pytest.mark.parametrize('route', ['text', 'file'])
@pytest.mark.parametrize('malformed', [False, True])
def test_oversized_unknown_or_malformed_import_does_not_materialize(repo, client, monkeypatch, route, malformed):
    # A materializer is forbidden even when the parser also reports malformed syntax.
    from card_data.sync import ScryfallSyncService
    def forbidden(*a, **k):
        pytest.fail('Rejected import must not materialize local knowledge')
    monkeypatch.setattr(ScryfallSyncService, 'sync_card_from_local_knowledge', forbidden)
    text = '60 Mountain\nSideboard:\n16 Island'+ ('\n! invalid syntax' if malformed else '')
    before, before_cards = rows(repo), cards(repo)
    if route == 'text':
        response = client.post('/decks/import', json={'name':'control', 'deck_text':text})
    else:
        response = client.post('/decks/import-file?name=control', files={'file':('deck.txt', text)})
    assert response.status_code == 422 and response.json()['detail']['code'] == 'sideboard_limit_exceeded'
    assert rows(repo) == before and cards(repo) == before_cards


def test_malformed_legacy_receipt_is_readonly(repo, client, monkeypatch):
    from card_data.sync import ScryfallSyncService
    def forbidden(*a, **k):
        pytest.fail('Parser-rejected import must not materialize local knowledge')
    monkeypatch.setattr(ScryfallSyncService, 'sync_card_from_local_knowledge', forbidden)
    before, before_cards = rows(repo), cards(repo)
    response = client.post('/decks/import', json={'name':'invalid', 'deck_text':'4 Lightning Bolt\n! invalid'})
    assert response.status_code == 200 and response.json()['errors'] and response.json()['deck_id'] is None
    assert rows(repo) == before and cards(repo) == before_cards


@pytest.mark.parametrize('code,front,expected', FAMILIES)
def test_generic_explicit_case_identity_remains_distinct(repo, client, code, front, expected):
    item = prepare(repo, None, code, front, 'offline')
    results = [client.post('/decks/import', json={'name':item['deck_name'], 'deck_text':item['deck_text'], 'source':source}).json()
        for source in ['expansion_top:'+code.lower(), 'EXPANSION_TOP:'+code, 'user', 'user']]
    assert len({r['deck_id'] for r in results}) == 4
    before = rows(repo)
    response = client.post('/decks/import', json={'name':item['deck_name'], 'deck_text':item['deck_text'], 'source':'EXPANSION_TOP:'+code})
    assert response.json()['deck_id'] == results[1]['deck_id'] and rows(repo) == before


@pytest.mark.parametrize('mode', ['offline', 'missing'])
def test_actual_restart_root_receipts_and_inventory(tmp_path, mode):
    root = tmp_path/mode; root.mkdir()
    worker = Path(__file__).with_name('import_identity_fix_worker.py')
    env = {**os.environ, 'PYTHONPATH':str(worker.parents[1]), 'MTG_DEBUG_HANDS':'0'}
    evidence = []
    for phase in ['seed', 'restart']:
        result = subprocess.run([sys.executable, str(worker), phase, mode, str(root)], env=env, capture_output=True, text=True, timeout=90)
        (root/(phase+'.log')).write_text(result.stdout+result.stderr)
        assert result.returncode == 0, result.stdout+result.stderr
        evidence.append(json.loads((root/(phase+'-evidence.json')).read_text()))
    assert evidence[0]['pid'] != evidence[1]['pid']
    assert evidence[0]['snapshot_hash'] == evidence[1]['snapshot_hash']
    assert evidence[0]['semantic_inventory_hash'] == evidence[1]['semantic_inventory_hash']
