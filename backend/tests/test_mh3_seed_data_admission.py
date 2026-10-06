"""Exact canonical metadata append, not runtime mechanics certification."""
import hashlib
import json
from pathlib import Path
import pickle
import socket

import pytest

from card_data.fallback_cards import fallback_card_payload
from card_data.hydration import hydrate_deck_cards, ready_for_match
from decks.catalog import event_record, load_catalog
from game_state.state import MatchFactory
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from scripts.export_builtin_oracle_seed import shipped_names
from tests.test_builtin_metadata_refresh import repo
from tests.generic_import_fixtures import client
from ai.deck_analysis import analyze_deck

BASE = Path(__file__).parent/'fixtures/mh3_seed_gap/seed119_before.json'
DATA = Path(__file__).parents[1]/'card_data'
BEFORE = json.loads(BASE.read_text())
SEED = json.loads((DATA/'builtin_oracle_seed.json').read_text())
LEDGER = json.loads((DATA/'mh3_catalog_seed_provenance.json').read_text())
ADDED = [r['requested_name'] for r in LEDGER['records']]
RAW = load_catalog()['cards']
digest = lambda r: hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args,**kwargs):
        raise AssertionError('Offline data qualification must not connect externally')
    monkeypatch.setattr(socket.socket,'connect',forbidden)


def test_all119_whole_properties_and_source_unchanged_exact_append36():
    assert len(BEFORE['cards']) == 119 and len(SEED['cards']) == 155
    assert list(SEED['cards'])[:119] == list(BEFORE['cards'])
    assert {n:SEED['cards'][n] for n in BEFORE['cards']} == BEFORE['cards']
    assert {k:v for k,v in SEED.items() if k!='cards'} == {k:v for k,v in BEFORE.items() if k!='cards'}
    assert set(SEED['cards'])-set(BEFORE['cards']) == set(ADDED) and len(ADDED) == 36
    assert hashlib.sha256(BASE.read_bytes()).hexdigest() == LEDGER['baseline_seed_sha256']
    assert hashlib.sha256((DATA/'builtin_oracle_seed.json').read_bytes()).hexdigest() == LEDGER['seed_sha256']
    assert LEDGER['network_fetches'] == 0 and LEDGER['derived_facts_added'] is False
    assert len(shipped_names()) == 155 and all(fallback_card_payload(n) for n in shipped_names())


@pytest.mark.parametrize('name',ADDED)
def test_full_raw_ID_Oracle_stats_colors_and_provenance_exact(name):
    evidence=next(r for r in LEDGER['records'] if r['requested_name']==name)
    raw=RAW[evidence['scryfall_id']]
    payload=fallback_card_payload(name)
    assert payload == {**raw,'scryfall_id':raw['id']}
    assert digest(raw) == evidence['canonical_raw_sha256']
    assert digest(payload) == evidence['seed_payload_sha256']
    assert raw['oracle_id'] == evidence['oracle_id'] and evidence['runtime_effect_certificate'] is False
    assert not evidence['field_derivations'] and raw['object']=='card'
    fixture=next(r for r in map(json.loads,(Path(__file__).parent/'fixtures/historical_event_catalog/canonical.jsonl').read_text().splitlines()) if r['id']==raw['id'])
    assert raw == fixture
    assert ready_for_match(payload)


@pytest.mark.parametrize('code',['OTJ','MH3'])
def test_actual_HTTP_global_seed_import75_analysis_inventory_and_root_restore(repo,client,code):
    before_cache=[r.model_dump(mode='json') for r in repo.list_cards()]
    out=client.post(f'/decks/expansion-top/{code}/import').json()
    assert not out['errors'] and not out['suggestions']
    board=out['mainboard']+out['sideboard']
    hydrated=hydrate_deck_cards(repo,board)
    assert sum(c['quantity'] for c in hydrated)==75
    assert all(ready_for_match(c) and c['card_data_sources']==['offline_seed'] for c in hydrated)
    assert out['analysis']==analyze_deck(hydrate_deck_cards(repo,out['mainboard']))
    rows=event_record(code)['mainboard']+event_record(code)['sideboard']
    assert {r['canonical_name'] for r in rows} == {c['name'] for c in hydrated}
    state=MatchFactory.from_decks(hydrate_deck_cards(repo,out['mainboard']),hydrate_deck_cards(repo,out['mainboard']),seed=716)
    before=pickle.dumps(state)
    assert serialize_match_snapshot(deserialize_match_snapshot(serialize_match_snapshot(state)))==serialize_match_snapshot(state)
    assert pickle.dumps(state)==before
    repeat=client.post(f'/decks/expansion-top/{code}/import').json()
    assert repeat['deck_id']==out['deck_id']
    assert [r.model_dump(mode='json') for r in repo.list_cards()]==before_cache
    assert repo.list_card_knowledge_names()==[]
