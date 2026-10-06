"""Canonical expansion-template admission, not template-name or mechanics claims."""
import hashlib
import json
import os
from pathlib import Path

import pytest

from ai.deck_analysis import analyze_deck
from card_data import hydration
from decks import bootstrap
from decks.expansion_top_decks import EXPANSION_TOP_DECKS
from decks.service import DeckService
from tests.test_builtin_metadata_refresh import repo, rows, seed_cache

FAMILIES = [('LEA', 'Burn'), ('DRK', 'Control'), ('USG', 'Ramp'), ('ONS', 'Tribal')]
TRACE = []


def entry(code):
    return next(item for item in EXPANSION_TOP_DECKS if item['code'] == code)


def cache_rows(repo):
    return [r.model_dump(mode='json') for r in repo.list_cards()]


def actual_admission(repo, board):
    canonical = hydration.hydrate_deck_cards(repo, board)
    analysis = analyze_deck(canonical)
    admitted = (bool(canonical) and all(c.get('card_data_sources') and hydration.ready_for_match(c) for c in canonical)
                and analysis['type_metadata_coverage'] == 1 and analysis['confidence'] > 0
                and not {'missing_card_metadata', 'partial_card_metadata', 'fallback_midrange'}.intersection(analysis['signals']))
    return canonical, analysis, admitted


def assert_provenance(result, canonical, analysis, admitted):
    assert result['analysis'] == analysis
    assert result['classification_status'] == ('resolved' if admitted else 'unknown')
    assert result['archetype_guess'] == (analysis['primary_archetype'] if admitted else 'unknown')
    p = result['classification_provenance']
    assert p['method'] == 'ai.deck_analysis.analyze_deck'
    assert p['facts_method'] == 'card_data.hydration.hydrate_deck_cards'
    assert p['admission'] == 'complete-local-canonical-v1'
    assert p['sources'] == sorted({s for c in canonical for s in c.get('card_data_sources', [])})
    assert p['cards'] == [{'card_name': c['card_name'], 'sources': c['card_data_sources'],
                          'ready_for_match': bool(hydration.ready_for_match(c))} for c in canonical]
    assert p['resolved_board_sha256'] == hashlib.sha256(json.dumps(canonical, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@pytest.mark.parametrize('code,expected', FAMILIES)
@pytest.mark.parametrize('mode', ['offline', 'canonical_cache'])
def test_admitted_import_and_repeat_startup_keep_actual_analysis_and_provenance(repo, monkeypatch, code, expected, mode):
    item = entry(code)
    monkeypatch.setattr(bootstrap, 'EXPANSION_TOP_DECKS', [item])
    service = DeckService(repo)
    parsed = service.parser.parse(item['deck_text'])
    assert not parsed.errors
    if mode == 'canonical_cache':
        seed_cache(repo, parsed.mainboard + parsed.sideboard)
        monkeypatch.setattr(hydration, 'fallback_card_payload', lambda _: None)
    imported = service.import_expansion_top_deck(code)
    assert not imported['errors']
    canonical, analysis, admitted = actual_admission(repo, imported['mainboard'])
    assert admitted and analysis['primary_archetype'] == expected
    assert_provenance(imported, canonical, analysis, admitted)
    assert imported['classification_provenance']['sources'] == (['offline_seed'] if mode == 'offline' else ['cache'])
    before, before_cards = rows(repo), cache_rows(repo)
    for _ in range(2):
        bootstrap.ensure_expansion_top_decks(repo)
        assert rows(repo) == before and cache_rows(repo) == before_cards
    TRACE.append({'kind': 'admitted-repeat', 'code': code, 'template_label': item['archetype'],
                  'actual_label': expected, 'import': imported, 'canonical': canonical, 'mode': mode,
                  'all_row_fields_unchanged': True, 'cache_unchanged': True})


@pytest.mark.parametrize('code,expected', FAMILIES)
def test_positive_canonical_refresh_changes_only_latest_label_preserves_history_and_same_name_user(repo, monkeypatch, code, expected):
    item = entry(code)
    monkeypatch.setattr(bootstrap, 'EXPANSION_TOP_DECKS', [item])
    p = DeckService(repo).parser.parse(item['deck_text'])
    assert not p.errors
    history = repo.save_deck(item['deck_name'], 'expansion_top:' + code.lower(), p.mainboard, p.sideboard, 'Midrange')
    user = repo.save_deck(item['deck_name'], 'user', p.mainboard, p.sideboard, 'Midrange')
    latest = repo.save_deck(item['deck_name'], ' expansion_top:' + code + ' ', p.mainboard, p.sideboard, 'Midrange')
    before, before_cards = rows(repo), cache_rows(repo)
    canonical, analysis, admitted = actual_admission(repo, p.mainboard)
    assert admitted and analysis['primary_archetype'] == expected
    bootstrap.ensure_expansion_top_decks(repo)
    after = rows(repo)
    assert set(after) == set(before)
    for rid, old in before.items():
        desired = {**old, 'archetype_guess': expected} if rid == latest.id else old
        assert after[rid] == desired
    assert after[history.id] == before[history.id] and after[user.id] == before[user.id]
    assert cache_rows(repo) == before_cards
    bootstrap.ensure_expansion_top_decks(repo)
    assert rows(repo) == after
    TRACE.append({'kind': 'positive-refresh', 'code': code, 'canonical': canonical, 'analysis': analysis,
                  'changed_id': latest.id, 'before_label': 'Midrange', 'after_label': expected,
                  'history_id': history.id, 'user_id': user.id, 'only_label_changed': True})


@pytest.mark.parametrize('code', ['LEA', 'DRK'])
@pytest.mark.parametrize('mode', ['missing', 'partial_oracle', 'confidence', 'fallback_signal'])
def test_unadmitted_existing_label_is_historical_not_overwritten_or_certified(repo, monkeypatch, code, mode):
    item = entry(code)
    monkeypatch.setattr(bootstrap, 'EXPANSION_TOP_DECKS', [item])
    p = DeckService(repo).parser.parse(item['deck_text'])
    assert not p.errors
    if mode != 'missing':
        seed_cache(repo, p.mainboard + p.sideboard)
    monkeypatch.setattr(hydration, 'fallback_card_payload', lambda _: None)
    p = DeckService(repo).parser.parse(item['deck_text'])
    assert not p.errors
    row = repo.save_deck(item['deck_name'], 'expansion_top:' + code, p.mainboard, p.sideboard, 'Midrange')
    if mode == 'partial_oracle':
        cached = repo.get_cached_card_by_name('Lightning Bolt' if code == 'LEA' else 'Counterspell')
        assert cached
        cached.oracle_text = ''
        repo.session.commit()
    if mode in {'confidence', 'fallback_signal'}:
        original = bootstrap.analyze_deck
        def refused(deck):
            result = original(deck)
            return {**result, 'confidence': 0} if mode == 'confidence' else {**result, 'signals': result['signals'] + ['fallback_midrange']}
        monkeypatch.setattr(bootstrap, 'analyze_deck', refused)
    before, before_cards = rows(repo), cache_rows(repo)
    assert bootstrap._admitted_builtin_archetype(repo, p.mainboard) is None
    for _ in range(2):
        bootstrap.ensure_expansion_top_decks(repo)
        assert rows(repo) == before and cache_rows(repo) == before_cards
    canonical, analysis, admitted = actual_admission(repo, p.mainboard)
    if mode in {'missing', 'partial_oracle'}:
        assert not admitted
    TRACE.append({'kind': 'historical-unadmitted', 'code': code, 'mode': mode, 'canonical': canonical,
                  'analysis': analysis, 'startup_analysis': bootstrap.analyze_deck(canonical),
                  'preserved_historical_label': row.archetype_guess,
                  'startup_admitted': False, 'all_rows_unchanged': True})


@pytest.mark.parametrize('code', ['LEA', 'DRK'])
@pytest.mark.parametrize('mode', ['missing', 'partial_oracle'])
def test_new_unadmitted_catalog_import_is_explicit_unknown_and_stays_unknown(repo, monkeypatch, code, mode):
    item = entry(code)
    monkeypatch.setattr(bootstrap, 'EXPANSION_TOP_DECKS', [item])
    p = DeckService(repo).parser.parse(item['deck_text'])
    assert not p.errors
    if mode == 'partial_oracle':
        seed_cache(repo, p.mainboard + p.sideboard)
        row = repo.get_cached_card_by_name('Lightning Bolt' if code == 'LEA' else 'Counterspell')
        row.oracle_text = ''
        repo.session.commit()
    monkeypatch.setattr(hydration, 'fallback_card_payload', lambda _: None)
    before_cards = cache_rows(repo)
    bootstrap.ensure_expansion_top_decks(repo)
    records = repo.list_decks()
    assert len(records) == 1 and records[0].archetype_guess == 'unknown'
    before = rows(repo)
    bootstrap.ensure_expansion_top_decks(repo)
    assert rows(repo) == before and cache_rows(repo) == before_cards
    imported = DeckService(repo).import_deck_text(item['deck_name'], item['deck_text'], records[0].source)
    canonical, analysis, admitted = actual_admission(repo, imported['mainboard'])
    assert not admitted
    assert_provenance(imported, canonical, analysis, admitted)
    assert imported['deck_id'] == records[0].id
    TRACE.append({'kind': 'new-unknown', 'code': code, 'mode': mode, 'import': imported,
                  'canonical': canonical, 'startup_does_not_claim_template_label': True})


@pytest.fixture(scope='module', autouse=True)
def record_trace():
    yield
    path = os.environ.get('MTG_EXPANSION_CLASSIFICATION_TRACE')
    if path:
        Path(path).write_text(json.dumps({'schema_version': 1, 'cases': TRACE,
            'scope': 'local canonical metadata admission, not verified mechanics'}, indent=2) + '\n')
