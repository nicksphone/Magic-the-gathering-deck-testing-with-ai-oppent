"""Canonical metadata refresh contract on fresh SQL and original HTTP consumers."""
from copy import deepcopy
import json
import os
import pickle
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

import persistence.db  # Schema registration only: default engine must never connect.
from persistence.repository import Repository
from card_data import hydration
from card_data.fallback_cards import fallback_card_payload
from ai.agent import AIAgent
from ai.deck_analysis import analyze_deck
from ai.matchup_profiles import profile_for
from ai.action_contract import complete_action
from ai.information import decision_view, is_unknown
from decks import bootstrap
from decks.builtin_decks import BUILTIN_DECKS
from decks.service import DeckService
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action


FAMILIES = [('Burn', 'Burn'), ('Dimir Control', 'Control'), ('Ramp', 'Ramp'), ('Tribal', 'Tribal')]
TRACE = []


@pytest.fixture(params=['memory', 'file'])
def repo(request, tmp_path):
    options = {'connect_args': {'check_same_thread': False}}
    if request.param == 'memory':
        engine = create_engine('sqlite://', poolclass=StaticPool, **options)
    else:
        engine = create_engine('sqlite:///' + str(tmp_path / 'owned-test.sqlite'), **options)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield Repository(session)
    engine.dispose()


def rows(repo):
    return {row.id: row.model_dump(mode='json') for row in repo.list_decks()}


def builtin(repo, name):
    return next(row for row in repo.list_decks()
                if row.name.strip().lower() == name.lower() and row.source.strip().lower() == 'builtin')


def seed_cache(repo, board):
    for item in board:
        raw = fallback_card_payload(item['card_name'])
        assert raw and raw.get('scryfall_id')
        repo.upsert_card({'scryfall_id': raw['scryfall_id'], 'name': raw['name'],
                         'type_line': raw['type_line'], 'oracle_text': raw.get('oracle_text', ''),
                         'mana_cost': raw.get('mana_cost', ''), 'colors': ','.join(raw.get('colors') or []),
                         'layout': raw.get('layout', ''), 'power': raw.get('power'),
                         'toughness': raw.get('toughness'), 'loyalty': raw.get('loyalty'),
                         'card_faces_json': json.dumps(raw.get('card_faces') or [])})


def assert_only_guesses_changed(before, after):
    assert set(before) == set(after)
    changed = []
    for rid, old in before.items():
        new = after[rid]
        if old['archetype_guess'] != new['archetype_guess']:
            assert old['source'].strip().lower() == 'builtin'
            changed.append(rid)
        assert {k: v for k, v in old.items() if k != 'archetype_guess'} == {
            k: v for k, v in new.items() if k != 'archetype_guess'}
    return changed


@pytest.mark.parametrize('name,expected', FAMILIES)
@pytest.mark.parametrize('warm', [False, True])
def test_complete_local_metadata_refresh_only_guess_and_idempotent(repo, name, expected, warm):
    bootstrap.ensure_builtin_decks(repo)
    row = builtin(repo, name)
    board = json.loads(row.mainboard_json)
    cold = analyze_deck(DeckService(repo)._resolve_card_metadata(board))
    assert row.archetype_guess == expected
    assert cold['primary_archetype'] == expected
    assert cold['confidence'] > 0 and cold['type_metadata_coverage'] == 1
    if warm:
        seed_cache(repo, board)
    canonical = hydration.hydrate_deck_cards(repo, board)
    assert all(hydration.ready_for_match(card) and card['card_data_sources'] for card in canonical)
    analysis = analyze_deck(canonical)
    assert analysis['primary_archetype'] == expected
    assert analysis['confidence'] > 0 and analysis['type_metadata_coverage'] == 1
    before = rows(repo)
    cards = [r.model_dump(mode='json') for r in repo.list_cards()]
    bootstrap.ensure_builtin_decks(repo)
    TRACE.append({'kind': 'refresh-observation', 'name': name, 'warm_cache': warm,
                  'cold_analysis': cold, 'resolved_analysis': analysis,
                  'before_guess': before[row.id]['archetype_guess'],
                  'observed_after_guess': builtin(repo, name).archetype_guess,
                  'expected_resolved_guess': expected})
    assert builtin(repo, name).archetype_guess == expected
    after = rows(repo)
    assert_only_guesses_changed(before, after)
    assert [r.model_dump(mode='json') for r in repo.list_cards()] == cards
    bootstrap.ensure_builtin_decks(repo)
    assert rows(repo) == after
    TRACE.append({'kind': 'complete', 'name': name, 'warm_cache': warm, 'cold_analysis': cold,
                  'resolved_analysis': analysis, 'canonical_records': canonical,
                  'before_guess': before[row.id]['archetype_guess'], 'after_guess': after[row.id]['archetype_guess'],
                  'row_id_preserved': True, 'all_non_guess_columns_and_card_cache_unchanged': True})


def test_no_local_metadata_preserves_cold_unknown_analysis_and_all_rows(repo, monkeypatch):
    bootstrap.ensure_builtin_decks(repo)
    before = rows(repo)
    monkeypatch.setattr(hydration, 'fallback_card_payload', lambda name: None)
    deck = hydration.hydrate_deck_cards(repo, json.loads(builtin(repo, 'Burn').mainboard_json))
    analysis = analyze_deck(deck)
    assert analysis['confidence'] == analysis['type_metadata_coverage'] == 0
    bootstrap.ensure_builtin_decks(repo)
    assert rows(repo) == before and not repo.list_cards()


@pytest.mark.parametrize('missing', ['card', 'oracle_text', 'power', 'face'])
def test_partial_data_never_refreshes_even_with_full_type_coverage(repo, monkeypatch, missing):
    bootstrap.ensure_builtin_decks(repo)
    name = 'Tempo' if missing == 'face' else 'Burn'
    row = builtin(repo, name)
    board = json.loads(row.mainboard_json)
    seed_cache(repo, board)
    # Existing parser resolves cached face aliases; stabilize that pre-existing inventory sync first.
    board = DeckService(repo).parser.parse(BUILTIN_DECKS[name]).mainboard
    row.mainboard_json = json.dumps(board)
    repo.session.add(row)
    repo.session.commit()
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
    original = hydration.fallback_card_payload
    monkeypatch.setattr(hydration, 'fallback_card_payload',
                        lambda n: None if n.split(' // ', 1)[0] == target else original(n))
    deck = hydration.hydrate_deck_cards(repo, board)
    assert not all(hydration.ready_for_match(card) for card in deck)
    before = rows(repo)
    bootstrap.ensure_builtin_decks(repo)
    assert rows(repo)[row.id] == before[row.id]


def test_zero_confidence_analysis_is_not_a_refresh_certificate(repo, monkeypatch):
    bootstrap.ensure_builtin_decks(repo)
    # Inject only an unknown-confidence analysis result, not card facts or a guessed quality label.
    original = analyze_deck
    def no_confidence(deck):
        actual = original(deck)
        return {**actual, 'confidence': 0}
    monkeypatch.setattr('ai.deck_analysis.analyze_deck', no_confidence)
    # Bootstrap imports the analyzer at module scope in the qualified implementation.
    if hasattr(bootstrap, 'analyze_deck'):
        monkeypatch.setattr(bootstrap, 'analyze_deck', no_confidence)
    before = rows(repo)
    bootstrap.ensure_builtin_decks(repo)
    assert rows(repo) == before


def test_latest_normalized_builtin_only_custom_and_history_inventory_unchanged(repo):
    bootstrap.ensure_builtin_decks(repo)
    original = builtin(repo, 'Burn')
    board, side = json.loads(original.mainboard_json), json.loads(original.sideboard_json)
    # Real existing canonical board, distinct ownership records; no invented cards.
    latest = repo.save_deck(' bUrN ', ' BuIlTiN ', board, side, 'Midrange')
    custom = [repo.save_deck('Burn', source, board, side, 'Control') for source in ['user', 'file', 'custom']]
    before = rows(repo)
    bootstrap.ensure_builtin_decks(repo)
    after = rows(repo)
    assert after[latest.id]['archetype_guess'] == 'Burn'
    assert after[original.id] == before[original.id]
    assert all(after[r.id] == before[r.id] for r in custom)
    assert_only_guesses_changed(before, after)
    bootstrap.ensure_builtin_decks(repo)
    assert rows(repo) == after


@pytest.mark.parametrize('pair', [('Burn', 'Dimir Control'), ('Ramp', 'Tribal')])
@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('controllers', [('human', 'ai'), ('ai', 'human')])
def test_http_original_consumer_profile_parity_before_after_refresh(repo, monkeypatch, pair, reverse, controllers):
    import main
    monkeypatch.setattr(main, 'ACTIVE_MATCHES', {})
    monkeypatch.setattr(main.app, 'dependency_overrides', {main.get_repo: lambda: repo})
    def forbidden(*args, **kwargs):
        raise AssertionError('No application lifespan/default DB')
    monkeypatch.setattr(main, 'init_db', forbidden)
    monkeypatch.setattr(main.app.router, 'lifespan_context', forbidden)
    names = pair[::-1] if reverse else pair
    bootstrap.ensure_builtin_decks(repo)
    entries = [builtin(repo, name) for name in names]
    boards = [json.loads(row.mainboard_json) for row in entries]
    for board in boards:
        seed_cache(repo, board)
    before_rows = rows(repo)
    ctor, choices = [], []
    original_init, original_choose = AIAgent.__init__, AIAgent.choose_action
    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        ctor.append({'own': self.archetype, 'opponent': self.opponent_archetype,
                     'profile': deepcopy(self.matchup_profile)})
    def choose(self, state, moves, seat):
        root = pickle.dumps(state, 5)
        private, _ = decision_view(state, seat, moves)
        assert set(private.starting_decks) == {seat}
        hidden = state.players[3-seat].hand + state.players[1].library + state.players[2].library
        assert all(is_unknown(private.cards[cid]) and not private.cards[cid].name for cid in hidden)
        result = original_choose(self, state, moves, seat)
        action = complete_action(result.action)
        checked_action(deepcopy(state), self.engine, seat, deepcopy(action))
        assert pickle.dumps(state, 5) == root
        choices.append({'seat': seat, 'action': action, 'reasoning': result.reasoning,
                        'root_unchanged': True, 'checked_legal': True})
        return result
    monkeypatch.setattr(AIAgent, '__init__', init)
    monkeypatch.setattr(AIAgent, 'choose_action', choose)
    client = TestClient(main.app)  # No lifespan/context entry or listening socket.
    try:
        analyses = [client.post('/decks/analyze', json={'deck': b}).json() for b in boards]
        expected = [a['primary_archetype'] for a in analyses]
        assert all(a['confidence'] > 0 and a['type_metadata_coverage'] == 1 for a in analyses)
        payload = {'deck_a': boards[0], 'deck_b': boards[1], 'deck_a_id': entries[0].id,
                   'deck_b_id': entries[1].id, 'controller_a': controllers[0], 'controller_b': controllers[1],
                   'seed': 413, 'ai_difficulty': 'master'}
        results = []
        for stage in ['before', 'after']:
            if stage == 'after':
                bootstrap.ensure_builtin_decks(repo)
                assert [builtin(repo, n).archetype_guess for n in names] == expected
                assert_only_guesses_changed(before_rows, rows(repo))
            response = client.post('/matches/start', json=payload, headers={'Idempotency-Key': stage})
            assert response.status_code == 200, response.text
            mid = response.json()['id']; match = main.ACTIVE_MATCHES[mid]
            assert response.json()['root_seed'] is None
            for seat, controller in match.controllers.items():
                if controller == 'ai':
                    assert response.json()['players'][str(seat)]['hand'] == []
            actor = main._default_player_for_state(match)
            if match.controllers[actor] == 'human':
                human = client.post(f'/matches/{mid}/action', json={'player_id': actor, 'action': {'type': 'keep_hand'}})
                assert human.status_code == 200, human.text
            tick = client.post(f'/matches/{mid}/autoplay', params={'ticks': 1})
            assert tick.status_code == 200, tick.text
            saved_state = serialize_match_snapshot(match.state)
            saved_config = main._controller_snapshot(match)
            main.ACTIVE_MATCHES.pop(mid)
            restored = client.post('/matches/start', json=payload, headers={'Idempotency-Key': stage})
            assert restored.status_code == 200, restored.text
            assert serialize_match_snapshot(main.ACTIVE_MATCHES[mid].state) == saved_state
            assert main._controller_snapshot(main.ACTIVE_MATCHES[mid]) == saved_config
            results.append({'stage': stage, 'constructors': deepcopy(ctor[-4:]), 'decision': deepcopy(choices[-1]),
                            'restart_complete_state_equal': True})
            TRACE.append({'kind': 'http-stage', 'names': names, 'controllers': controllers,
                          'stored_guesses': [builtin(repo, n).archetype_guess for n in names],
                          'resolved_analysis': analyses, **results[-1]})
        expected_ctor = [{'own': expected[i], 'opponent': expected[1-i],
                          'profile': profile_for(expected[i], expected[1-i])} for i in range(2)] * 2
        assert results[0]['constructors'] == results[1]['constructors'] == expected_ctor
        assert results[0]['decision'] == results[1]['decision']
        TRACE.append({'kind': 'http-parity', 'names': names, 'controllers': controllers,
                      'resolved_analysis': analyses, 'results': results, 'authoritative_style_unchanged': True})
    finally:
        client.close()


@pytest.fixture(scope='module', autouse=True)
def trace():
    yield
    path = os.environ.get('MTG_BOOTSTRAP_REFRESH_TRACE')
    if path:
        Path(path).write_text(json.dumps({'schema_version': 1, 'cases': TRACE}, indent=2) + '\n')
