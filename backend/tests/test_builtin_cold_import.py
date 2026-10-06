"""First bootstrap labels must have the same local admission as later refreshes."""
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai.deck_analysis import analyze_deck
from card_data import hydration
from decks import bootstrap
from decks.builtin_decks import BUILTIN_DECKS
from decks.service import DeckService
from tests.test_builtin_metadata_refresh import (
    FAMILIES, builtin, repo, rows, seed_cache, assert_only_guesses_changed,
    test_http_original_consumer_profile_parity_before_after_refresh as http_contract,
)
import tests.test_builtin_metadata_refresh as refresh_evidence

TRACE = []


def boards(repo):
    parser = DeckService(repo).parser
    return {name: parser.parse(text) for name, text in BUILTIN_DECKS.items()}


def cache_all(repo):
    for parsed in boards(repo).values():
        assert not parsed.errors
        seed_cache(repo, parsed.mainboard + parsed.sideboard)


def cards(repo):
    return [r.model_dump(mode='json') for r in repo.list_cards()]


@pytest.mark.parametrize('mode', ['offline', 'canonical_cache', 'unknown'])
@pytest.mark.parametrize('name,expected', FAMILIES)
def test_first_import_matches_actual_admitted_local_analysis(repo, monkeypatch, mode, name, expected):
    assert not repo.list_decks() and not repo.list_cards()
    if mode == 'canonical_cache':
        cache_all(repo)
    if mode != 'offline':
        monkeypatch.setattr(hydration, 'fallback_card_payload', lambda _: None)
    parsed = boards(repo)
    before_cards = cards(repo)
    bootstrap.ensure_builtin_decks(repo)
    row = builtin(repo, name)
    canonical = hydration.hydrate_deck_cards(repo, json.loads(row.mainboard_json))
    analysis = analyze_deck(canonical)
    admitted = all(c['card_data_sources'] and hydration.ready_for_match(c) for c in canonical)
    if mode == 'unknown':
        assert not admitted and analysis['confidence'] == analysis['type_metadata_coverage'] == 0
        assert row.archetype_guess == 'unknown'
    else:
        assert admitted and analysis['confidence'] > 0 and analysis['type_metadata_coverage'] == 1
        assert analysis['primary_archetype'] == row.archetype_guess == expected
    assert set(r.name for r in repo.list_decks()) == set(BUILTIN_DECKS)
    for item in repo.list_decks():
        assert json.loads(item.mainboard_json) == parsed[item.name].mainboard
        assert json.loads(item.sideboard_json) == parsed[item.name].sideboard
    assert cards(repo) == before_cards
    before = rows(repo)
    bootstrap.ensure_builtin_decks(repo)
    assert rows(repo) == before and cards(repo) == before_cards
    TRACE.append({'kind': 'first-import', 'mode': mode, 'name': name,
                  'stored_guess': row.archetype_guess, 'actual_analysis': analysis,
                  'canonical_cards': canonical, 'admitted': admitted,
                  'inventory_preserved': True, 'cache_unchanged': True})


@pytest.mark.parametrize('missing', ['card', 'oracle_text', 'power', 'face'])
def test_first_partial_cache_never_claims_concrete_label_then_recovers(repo, monkeypatch, missing):
    cache_all(repo)
    name = 'Tempo' if missing == 'face' else 'Burn'
    target = {'card': 'Lightning Bolt', 'oracle_text': 'Lightning Bolt',
              'power': 'Monastery Swiftspear', 'face': 'Delver of Secrets'}[missing]
    cached = repo.get_cached_card_by_name(target)
    assert cached
    if missing == 'card':
        repo.session.delete(cached)
    elif missing == 'face':
        cached.card_faces_json = '[]'
    else:
        setattr(cached, missing, None if missing == 'power' else '')
    repo.session.commit()
    monkeypatch.setattr(hydration, 'fallback_card_payload', lambda _: None)
    before_cards = cards(repo)
    bootstrap.ensure_builtin_decks(repo)
    row = builtin(repo, name)
    resolved = hydration.hydrate_deck_cards(repo, json.loads(row.mainboard_json))
    assert not all(hydration.ready_for_match(card) for card in resolved)
    assert row.archetype_guess == 'unknown' and cards(repo) == before_cards
    before = rows(repo)
    bootstrap.ensure_builtin_decks(repo)
    assert rows(repo) == before
    seed_cache(repo, json.loads(row.mainboard_json))
    canonical = hydration.hydrate_deck_cards(repo, json.loads(row.mainboard_json))
    assert all(card['card_data_sources'] and hydration.ready_for_match(card) for card in canonical)
    expected = analyze_deck(canonical)
    bootstrap.ensure_builtin_decks(repo)
    assert builtin(repo, name).id == row.id
    assert builtin(repo, name).archetype_guess == expected['primary_archetype']
    assert_only_guesses_changed(before, rows(repo))


def test_new_zero_confidence_is_explicit_unknown(repo, monkeypatch):
    actual = bootstrap.analyze_deck
    monkeypatch.setattr(bootstrap, 'analyze_deck', lambda deck: {**actual(deck), 'confidence': 0})
    bootstrap.ensure_builtin_decks(repo)
    assert all(row.archetype_guess == 'unknown' for row in repo.list_decks())
    before = rows(repo)
    bootstrap.ensure_builtin_decks(repo)
    assert rows(repo) == before


@pytest.mark.parametrize('name,expected', FAMILIES)
def test_existing_latest_only_refresh_preserves_history_user_and_identity(repo, name, expected):
    parsed = boards(repo)[name]
    old = repo.save_deck(name, 'builtin', parsed.mainboard, parsed.sideboard, 'Midrange')
    latest = repo.save_deck(' '+name.swapcase()+' ', ' BuIlTiN ', parsed.mainboard, parsed.sideboard, 'unknown')
    custom = [repo.save_deck(name, source, parsed.mainboard, parsed.sideboard, 'Control')
              for source in ['user', 'file', 'custom']]
    before = rows(repo)
    bootstrap.ensure_builtin_decks(repo)
    after = rows(repo)
    assert after[old.id] == before[old.id]
    assert all(after[r.id] == before[r.id] for r in custom)
    assert after[latest.id]['archetype_guess'] == expected
    assert {k:v for k,v in after[latest.id].items() if k != 'archetype_guess'} == {
        k:v for k,v in before[latest.id].items() if k != 'archetype_guess'}
    bootstrap.ensure_builtin_decks(repo)
    assert rows(repo) == after


@pytest.mark.parametrize('mode', ['offline', 'canonical_cache'])
@pytest.mark.parametrize('pair', [('Burn', 'Dimir Control'), ('Ramp', 'Tribal')])
@pytest.mark.parametrize('controllers', [('human', 'ai'), ('ai', 'human')])
def test_first_import_actual_http_repository_profile_and_restart(repo, monkeypatch, mode, pair, controllers):
    import main
    if mode == 'canonical_cache':
        cache_all(repo)
        monkeypatch.setattr(hydration, 'fallback_card_payload', lambda _: None)
    bootstrap.ensure_builtin_decks(repo)
    before = rows(repo)
    monkeypatch.setattr(main.app, 'dependency_overrides', {main.get_repo: lambda: repo})
    def forbidden(*a, **k):
        pytest.fail('No app startup or default database')
    monkeypatch.setattr(main, 'init_db', forbidden)
    monkeypatch.setattr(main.app.router, 'lifespan_context', forbidden)
    with_no_lifespan = TestClient(main.app)
    try:
        result = with_no_lifespan.get('/decks')
        assert result.status_code == 200
        entries = {r['id']:r for r in result.json()}
        for name in pair:
            row = builtin(repo, name)
            resolved = hydration.hydrate_deck_cards(repo, json.loads(row.mainboard_json))
            expected = analyze_deck(resolved)
            assert entries[row.id]['archetype_guess'] == expected['primary_archetype']
            assert expected['confidence'] > 0
    finally:
        with_no_lifespan.close()
    start = len(refresh_evidence.TRACE)
    # Existing strict contract forwards original policy, checks actor-private views,
    # checked_action legality, full pickle root purity, and persisted restart parity.
    http_contract(repo, monkeypatch, pair, False, controllers)
    assert rows(repo) == before
    TRACE.append({'kind': 'http-first-import', 'mode': mode, 'pair': pair,
                  'controllers': controllers, 'observations': deepcopy(refresh_evidence.TRACE[start:])})


@pytest.fixture(scope='module', autouse=True)
def trace():
    yield
    path = os.environ.get('MTG_COLD_BUILTIN_TRACE')
    if path:
        Path(path).write_text(json.dumps({'schema_version':1, 'cases':TRACE}, indent=2)+'\n')
