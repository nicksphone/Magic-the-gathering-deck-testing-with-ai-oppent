"""Local canonical admission, not arbitrary-card rules certification."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlmodel import Session

import main
from card_data.hydration import hydrate_deck_cards, ready_for_match
from card_data.service import CardService
from card_data.sync import ScryfallSyncService
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import MatchFactory
from persistence.db import engine
from persistence.repository import Repository
from scripts.sync_all_card_knowledge import import_cards
from tests.test_api_input_contracts import game, snapshot


REAL_HYDRATE = main._hydrate_deck_cards
ROWS = {row['name']: {'object': 'card', **row} for row in json.loads(
    (Path(__file__).parent / 'fixtures/proliferate.json').read_text())}


def forbid_network(monkeypatch):
    monkeypatch.setattr(ScryfallSyncService, 'sync_card_by_name', lambda *a, **k: pytest.fail('Match hydration attempted external sync'))
    monkeypatch.setattr('card_data.sync.get_with_backoff', lambda *a, **k: pytest.fail('Match hydration fetched external data'))


@pytest.mark.parametrize('name', ['Island', 'Memory Deluge', 'Brutal Cathar', 'Kumano Faces Kakkazan', "Imodane's Recruiter"])
def test_cold_seed_start_is_offline_and_has_live_diagnostic_parity(game, monkeypatch, name):
    client, controller = game
    monkeypatch.setattr(main, '_hydrate_deck_cards', REAL_HYDRATE)
    forbid_network(monkeypatch)
    deck = [{'card_name': name, 'quantity': 4}, {'card_name': 'Island', 'quantity': 56}]
    with Session(engine) as session:
        repo = Repository(session)
        before = len(repo.list_cards())
        live = REAL_HYDRATE(repo, deck)
        diagnostic = hydrate_deck_cards(repo, deck)
        assert live == diagnostic and ready_for_match(live[0])
        assert len(repo.list_cards()) == before
    result = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck, 'seed': 81}, headers={'Idempotency-Key': f'offline-{name}'})
    assert result.status_code == 200, result.text
    mid = result.json()['id']
    repeat = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck, 'seed': 81}, headers={'Idempotency-Key': f'offline-{name}'})
    assert repeat.status_code == 200 and repeat.json()['id'] == mid
    state = main.ACTIVE_MATCHES[mid].state
    card = next(card for card in state.cards.values() if card.name == name)
    assert len(card.card_faces) == len(live[0].get('card_faces') or [])
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.cards[card.id].card_faces == card.card_faces


def test_bulk_only_card_admission_does_not_materialize_database_cache(game, monkeypatch):
    client, controller = game
    monkeypatch.setattr(main, '_hydrate_deck_cards', REAL_HYDRATE)
    forbid_network(monkeypatch)
    with Session(engine) as session:
        repo = Repository(session)
        import_cards(repo, [ROWS['Contentious Plan']], {'source': 'scryfall'})
        before = len(repo.list_cards())
        report = CardService(repo).completeness_report(['Contentious Plan'])['cards'][0]
        assert report['match_ready'] and not report['needs_card_sync']
        assert 'local_knowledge' in report['card_data_sources']
        assert not report['rulings']
        assert len(repo.list_cards()) == before
    deck = [{'card_name': 'Contentious Plan', 'quantity': 4}, {'card_name': 'Island', 'quantity': 56}]
    response = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck})
    assert response.status_code == 200, response.text
    with Session(engine) as session:
        assert Repository(session).get_cached_card_by_name('Contentious Plan') is None
    state = main.ACTIVE_MATCHES[response.json()['id']].state
    spell = next(card for card in state.cards.values() if card.name == 'Contentious Plan')
    assert spell.oracle_text == ROWS['Contentious Plan']['oracle_text']


def test_missing_card_admission_is_structured_and_does_not_partially_write(game, monkeypatch):
    client, controller = game
    monkeypatch.setattr(main, '_hydrate_deck_cards', REAL_HYDRATE)
    forbid_network(monkeypatch)
    with Session(engine) as session:
        import_cards(Repository(session), [ROWS['Contentious Plan']], {'source': 'scryfall'})
    before = snapshot(controller)
    active = set(main.ACTIVE_MATCHES)
    deck = [{'card_name': 'Contentious Plan', 'quantity': 4}, {'card_name': 'not a real card test name', 'quantity': 56}]
    response = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck})
    assert response.status_code == 422
    detail = response.json()['detail']
    assert detail['code'] == 'card_data_unavailable'
    assert detail['sync_endpoint'] == '/cards/sync-bulk'
    assert detail['cards'] == ['not a real card test name']
    assert snapshot(controller) == before and set(main.ACTIVE_MATCHES) == active


@pytest.mark.parametrize('faces_json', ['[]', 'null', '{}', 'invalid json'])
def test_partial_dfc_cache_recovers_canonical_seed_faces_without_fetch(faces_json, monkeypatch):
    forbid_network(monkeypatch)
    row = SimpleNamespace(name='Brutal Cathar', type_line='', oracle_text='', mana_cost=None,
                          layout='transform', colors='', card_faces_json=faces_json, image_uri=None)
    repo = SimpleNamespace(get_cached_cards_by_names=lambda names: {'brutal cathar': row})
    metadata = REAL_HYDRATE(repo, [{'card_name': 'Brutal Cathar', 'quantity': 4}])[0]
    assert ready_for_match(metadata)
    assert len(metadata['card_faces']) == 2
    assert metadata['mana_cost'] == '{2}{W}'
    assert metadata['power'] == '2'


def test_face_layout_without_canonical_faces_fails_closed():
    assert not ready_for_match({'type_line': 'Creature', 'layout': 'transform'})
    assert not ready_for_match({'type_line': 'Creature', 'layout': 'modal_dfc', 'card_faces': [{}]})
    assert not ready_for_match({'type_line': 'Token Creature', 'layout': 'token'})


def test_empty_readiness_query_does_not_scan_entire_knowledge_corpus(game, monkeypatch):
    client, controller = game
    monkeypatch.setattr(Repository, 'list_card_knowledge', lambda *a, **k: pytest.fail('Empty names scanned knowledge'))
    monkeypatch.setattr(Repository, 'get_card_knowledge_by_names', lambda *a, **k: pytest.fail('Empty names scanned knowledge'))
    response = client.get('/cards/completeness')
    assert response.status_code == 200 and response.json()['requested'] == 0


@pytest.mark.parametrize('names', [['a'*201], ['Island']*251])
def test_readiness_query_is_bounded_before_loading_data(game, monkeypatch, names):
    client, controller = game
    monkeypatch.setattr(CardService, 'completeness_report', lambda *a: pytest.fail('Invalid query reached data layer'))
    response = client.get('/cards/completeness', params=[('names', name) for name in names])
    assert response.status_code == 422


@pytest.mark.parametrize('failure', ['manual', 'wrong-id', 'bad-json', 'invalid-faces'])
def test_local_knowledge_requires_canonical_profile_without_fabricating_missing_card(failure, monkeypatch):
    forbid_network(monkeypatch)
    raw = dict(ROWS['Contentious Plan'])
    if failure == 'invalid-faces':
        raw['card_faces'] = 'not a face array'
    row = SimpleNamespace(name=raw['name'], oracle_source='manual' if failure == 'manual' else 'scryfall',
                          scryfall_id='mismatched' if failure == 'wrong-id' else raw['id'],
                          profiles_json='invalid' if failure == 'bad-json' else json.dumps({'card_data': raw}))
    repo = SimpleNamespace(get_cached_cards_by_names=lambda names: {}, list_card_knowledge=lambda names: [row])
    metadata = hydrate_deck_cards(repo, [{'card_name': raw['name'], 'quantity': 4}])[0]
    assert not ready_for_match(metadata)
    assert not metadata.get('oracle_text') and metadata['card_data_sources'] == []


def test_readiness_reports_canonical_vanilla_empty_text_and_no_rulings_claim(game, monkeypatch):
    client, controller = game
    with Session(engine) as session:
        raw = json.loads((Path(__file__).parent / 'fixtures/offline_hydration.json').read_text())[0]
        import_cards(Repository(session), [raw], {'source': 'scryfall'})
    response = client.get('/cards/completeness', params=[('names', 'Grizzly Bears')])
    assert response.status_code == 200
    card = response.json()['cards'][0]
    assert card['oracle_source'] == 'knowledge' and card['oracle']
    assert card['match_ready'] and card['image_status'] == 'remote'
    assert not card['rulings']


def test_bulk_planeswalker_preserves_printed_root_loyalty(game, monkeypatch):
    forbid_network(monkeypatch)
    raw = next(row for row in json.loads((Path(__file__).parent / 'fixtures/counter_prohibitions.json').read_text())
               if row['name'] == "Elspeth, Sun's Champion")
    with Session(engine) as session:
        repo = Repository(session)
        import_cards(repo, [raw], {'source': 'scryfall'})
        metadata = hydrate_deck_cards(repo, [{'card_name': raw['name'], 'quantity': 1}])[0]
        assert metadata['loyalty'] == raw['loyalty']
        assert ready_for_match(metadata)
        state = MatchFactory.from_decks([metadata], [metadata], seed=29)
        assert all(card.loyalty == int(raw['loyalty']) for card in state.cards.values())


@pytest.mark.parametrize('metadata', [
    {'type_line': 'Creature', 'power': None, 'toughness': '2'},
    {'type_line': 'Planeswalker', 'loyalty': None},
    {'type_line': 'Sorcery', 'card_faces': [{}, {}]},
])
def test_missing_printed_stats_and_unknown_face_layout_are_not_ready(metadata):
    assert not ready_for_match(metadata)


def test_nullable_loyalty_migration_preserves_rows_and_is_repeatable(tmp_path, monkeypatch):
    import persistence.db as db
    from sqlmodel import create_engine
    temporary = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with temporary.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE cardcache (name TEXT)')
        conn.exec_driver_sql("INSERT INTO cardcache VALUES ('Island')")
    monkeypatch.setattr(db, 'engine', temporary)
    db._ensure_card_cache_columns()
    db._ensure_card_cache_columns()
    with temporary.connect() as conn:
        assert conn.exec_driver_sql('SELECT name, loyalty FROM cardcache').one() == ('Island', None)
    temporary.dispose()


def test_explicit_local_sync_persists_printed_loyalty(game, monkeypatch):
    forbid_network(monkeypatch)
    raw = next(row for row in json.loads((Path(__file__).parent / 'fixtures/counter_prohibitions.json').read_text())
               if row['name'] == "Elspeth, Sun's Champion")
    with Session(engine) as session:
        repo = Repository(session)
        import_cards(repo, [raw], {'source': 'scryfall'})
        sync = ScryfallSyncService(repo)
        assert sync.sync_card_from_local_knowledge(raw['name'])
        cached = repo.get_cached_card_by_name(raw['name'])
        assert cached.loyalty == raw['loyalty']
        assert sync._serialize_card(cached)['loyalty'] == raw['loyalty']


@pytest.mark.parametrize('alias', ['Bala Ged Recovery', 'Bala Ged Sanctuary', 'bala ged recovery'])
def test_bulk_face_aliases_are_offline_and_allow_explicit_back_land_selection(game, monkeypatch, alias):
    from rules_engine.engine import RulesEngine
    from rules_engine.action_validation import checked_action
    from tests.test_restricted_mana import clean
    from game_state.state import Zone
    forbid_network(monkeypatch)
    raw = next(row for row in json.loads((Path(__file__).parent / 'fixtures/offline_hydration.json').read_text())
               if row['layout'] == 'modal_dfc')
    with Session(engine) as session:
        repo = Repository(session)
        import_cards(repo, [raw], {'source': 'scryfall'})
        assert repo.get_card_knowledge(alias).scryfall_id == raw['id']
        metadata = hydrate_deck_cards(repo, [{'card_name': alias, 'quantity': 1}])[0]
        assert ready_for_match(metadata) and len(metadata['card_faces']) == 2
        report = CardService(repo).completeness_report([alias])['cards'][0]
        assert report['oracle_source'] == 'knowledge' and report['match_ready'] and report['mana_cost']
        assert repo.get_cached_card_by_name(alias) is None
    state = clean()
    card = next(c for c in MatchFactory.from_decks([metadata], [metadata], seed=71).cards.values() if c.owner == 1)
    card.id = state.allocate_object_id()
    card.move_to_zone(Zone.HAND)
    state.cards[card.id] = card
    state.players[1].hand.append(card.id)
    move = next(move for move in RulesEngine().legal_moves(state, 1)
                if move['type'] == 'play_land' and move.get('card_id') == card.id and move.get('selected_face_index') == 1)
    state = checked_action(state, RulesEngine(), 1, move)
    assert state.cards[card.id].name == raw['card_faces'][1]['name']
    assert state.cards[card.id].types == ['Land']


def test_face_alias_lookup_does_not_accept_sql_wildcards_as_names(game):
    with Session(engine) as session:
        repo = Repository(session)
        assert repo.get_card_knowledge_by_names(['%', '_']) == {}
        assert repo.get_cached_cards_by_names(['%', '_']) == {}


@pytest.mark.parametrize('force', [False, True])
def test_sync_routes_forward_explicit_refresh_without_hydration(game, monkeypatch, force):
    client, _ = game
    calls = []
    def sync(service, name, force=False):
        calls.append((name, force))
        return {'name': name}
    monkeypatch.setattr(ScryfallSyncService, 'sync_card_by_name', sync)
    assert client.post('/cards/sync', params={'name': 'Island', 'force': force}).status_code == 200
    response = client.post('/cards/sync-bulk', json={
        'names': ['Island'], 'include_builtins': False,
        'include_saved_decks': False, 'include_expansion_top_decks': False, 'force': force,
    })
    assert response.status_code == 200 and response.json()['synced'] == 1
    assert calls == [('Island', force), ('Island', force)]


def test_local_art_does_not_short_circuit_incomplete_printed_loyalty(monkeypatch):
    from tests.test_card_image_sync import _DummyRepo, _CachedCard
    import httpx
    cached = _CachedCard()
    cached.type_line = 'Legendary Planeswalker'
    cached.name = 'Incomplete cache fixture'
    cached.loyalty = None
    service = ScryfallSyncService(_DummyRepo(cached))
    monkeypatch.setattr(service, '_cached_image_available', lambda uri: True)
    attempted = []
    def unavailable(*args, **kwargs):
        attempted.append(True)
        raise httpx.ConnectError('Offline explicit sync fixture')
    monkeypatch.setattr('card_data.sync.get_with_backoff', unavailable)
    result = service.sync_card_by_name(cached.name)
    assert attempted and not ready_for_match(result)


@pytest.mark.parametrize('face', [
    {'name': 'Missing creature stats', 'type_line': 'Creature', 'toughness': '2'},
    {'name': 'Missing loyalty', 'type_line': 'Planeswalker'},
])
def test_incomplete_second_face_is_not_match_ready(face):
    assert not ready_for_match({'type_line': 'Sorcery', 'layout': 'modal_dfc', 'card_faces': [
        {'name': 'Front metadata fixture', 'type_line': 'Sorcery'}, face,
    ]})


def test_legacy_split_colors_require_canonical_repair_before_admission():
    assert not ready_for_match({'type_line': 'Instant', 'layout': 'split', 'card_faces': [
        {'name': 'Cache fixture half A', 'type_line': 'Instant', 'mana_cost': '{R}', 'colors': []},
        {'name': 'Cache fixture half B', 'type_line': 'Instant', 'mana_cost': '{U}', 'colors': []},
    ]})
