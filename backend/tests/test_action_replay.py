"""Read-only checked replay and first-divergence reporting without AI search."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from analytics.action_replay import ReplayMismatch, reconstruct_game
from analytics.replay_tools import normalize_log_line
from game_state.state import MatchFactory, pregame_actor
from rules_engine.engine import RulesEngine
from tests.regression_agent_wave2.support import entry


def recorded(seed=937, starting_player=1):
    deck = [entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck, seed=seed)
    state.active_player = state.priority_player = starting_player
    state.mechanic_choice_players = {1, 2}
    rules = RulesEngine()
    for _ in range(80):
        pid = pregame_actor(state) if state.pregame_pending else state.priority_player
        legal = rules.legal_moves(state, pid)
        action = next((move for move in legal if move['type'] in {'keep_hand', 'play_land'}), {'type': 'pass_priority'})
        trace = {'pid': pid, 'turn': state.turn, 'step': str(state.step),
                 'active_player': state.active_player, 'priority_player': state.priority_player,
                 'hand': [state.cards[cid].name for cid in state.players[pid].hand],
                 'battlefield': [state.cards[cid].name for cid in state.players[pid].battlefield],
                 'legal_action_types': sorted({str(move['type']) for move in legal}), 'action': action}
        state.log.append('AI TRACE ' + json.dumps(trace, separators=(',', ':')))
        rules.take_action(state, pid, action, reject_invalid=True)
    log = [normalize_log_line(line) for line in state.log]
    return deck, {'seed': seed, 'starting_player': starting_player, 'winner': state.winner,
                  'turn': state.turn, 'ticks': 80, 'log': log,
                  'log_hash': hashlib.sha256('\n'.join(log).encode()).hexdigest()}


@pytest.mark.parametrize('starting_player', [1, 2])
def test_checked_reconstruction_matches_without_ai_or_input_mutation(monkeypatch, starting_player):
    from ai.agent import AIAgent
    monkeypatch.setattr(AIAgent, 'choose_action', lambda *_args: pytest.fail('Reconstruction must not search AI'))
    deck, game = recorded(starting_player=starting_player)
    before = deepcopy((deck, game))
    report = reconstruct_game(deck, deck, game)
    assert report['matched'] and report['decisions'] == 80
    assert sum(row['decisions'] for row in report['by_seat'].values()) == 80
    assert sum(row.get('play_land', 0) for row in report['by_seat'].values()) > 0
    assert sum(row.get('land_pass_opportunities', 0) for row in report['by_seat'].values()) == 0
    assert (deck, game) == before


@pytest.mark.parametrize('starting_player', [1, 2])
def test_private_observer_reports_both_hands_without_changing_replay(starting_player):
    deck, game = recorded(starting_player=starting_player)
    before = deepcopy((deck, game))
    seen = []
    report = reconstruct_game(deck, deck, game, decision_observer=seen.append)
    assert report == reconstruct_game(deck, deck, game)
    assert len(seen) == 80
    assert [row['decision'] for row in seen] == list(range(80))
    assert len(seen[0]['players']['1']['hand']) == len(seen[0]['players']['2']['hand']) == 7
    assert seen[0]['trace']['pid'] == starting_player
    for row in seen:
        actor = str(row['trace']['pid'])
        assert [card['name'] for card in row['players'][actor]['hand']] == row['trace']['hand']
        assert [card['name'] for card in row['players'][actor]['battlefield']] == row['trace']['battlefield']
        assert all('library' not in player for player in row['players'].values())
        json.dumps(row)
    assert (deck, game) == before


def test_observer_mutations_cannot_change_actions_or_effective_stats(monkeypatch):
    from game_state.serializers import serialize_card_view
    from tests.test_attack_bands import _state
    from tests.test_modal_spell_faces import fixture, ARCHAIC
    from game_state.state import Zone
    template = deepcopy(_state().cards['bears'])
    _, face_template = fixture(ARCHAIC)
    face_template = deepcopy(face_template)
    original = MatchFactory.from_decks
    created = []

    def constructed_board(*args, **kwargs):
        state = original(*args, **kwargs)
        card = deepcopy(template)
        card.owner = card.controller = 1
        card.counters['+1/+1'] = 1
        state.cards[card.id] = card
        state.players[1].battlefield.append(card.id)
        face = deepcopy(face_template)
        face.id = 'observed-faces'
        face.owner = face.controller = 1
        face.move_to_zone(Zone.BATTLEFIELD)
        state.cards[face.id] = face
        state.players[1].battlefield.append(face.id)
        created.append(state)
        return state

    monkeypatch.setattr(MatchFactory, 'from_decks', constructed_board)
    deck, game = recorded()
    seen = []

    def mutate(record):
        card = next(card for card in record['players']['1']['battlefield'] if card['id'] == 'bears')
        expected = serialize_card_view(created[-1], 'bears')
        assert {key: card[key] for key in expected} == expected
        assert (card['owner'], card['controller'], card['zone']) == (1, 1, 'battlefield')
        assert (card['base_power'], card['base_toughness']) == (2, 2)
        assert (card['power'], card['toughness']) == (3, 3)
        assert card['counters']['+1/+1'] == 1
        face = next(card for card in record['players']['1']['battlefield'] if card['id'] == 'observed-faces')
        assert face['card_faces'] == created[-1].cards['observed-faces'].card_faces
        seen.append(deepcopy(record))
        face['card_faces'][0]['oracle_text'] = 'observer mutation must not reach state'
        card['counters']['+1/+1'] = 99
        record['players']['1']['hand'].clear()
        record['players']['1']['mana_pool']['U'] = 999
        record['trace']['action']['type'] = 'invalid'
        record['legal_moves'].clear()
        record['blocks']['fabricated'] = ['bears']

    assert reconstruct_game(deck, deck, game, decision_observer=mutate) == reconstruct_game(deck, deck, game)
    assert len(seen) == 80


@pytest.mark.parametrize('field,value', [('hand', []), ('battlefield', ['Island']),
    ('turn', 99), ('step', 'invalid'), ('priority_player', 99), ('pid', 2),
    ('legal_action_types', []), ('action', {'type': 'cast_spell'})])
def test_trace_drift_identifies_first_bad_decision(field, value):
    deck, game = recorded()
    index = next(i for i, line in enumerate(game['log']) if line.startswith('AI TRACE '))
    trace = json.loads(game['log'][index][9:])
    trace[field] = value
    game['log'][index] = 'AI TRACE ' + json.dumps(trace)
    with pytest.raises(ReplayMismatch) as caught:
        reconstruct_game(deck, deck, game)
    assert caught.value.diagnostic['decision'] == 0
    assert caught.value.diagnostic['field'] == ('actor' if field == 'pid' else field)


def test_event_log_and_terminal_metadata_are_not_trusted_without_reconstruction():
    deck, game = recorded()
    altered = deepcopy(game)
    altered['log'].append('Fabricated event.')
    with pytest.raises(ReplayMismatch, match='log'):
        reconstruct_game(deck, deck, altered)
    for field, value in [('ticks', 81), ('turn', game['turn'] + 1), ('winner', 2), ('log_hash', '0' * 64)]:
        altered = {**game, field: value}
        with pytest.raises(ReplayMismatch) as caught:
            reconstruct_game(deck, deck, altered)
        assert caught.value.diagnostic['field'] == field


@pytest.mark.parametrize('field,value', [('seed', None), ('seed', True), ('starting_player', 99),
    ('starting_player', True), ('log', ['AI TRACE {}', 1]), ('winner', True)])
def test_malformed_record_metadata_is_rejected(field, value):
    deck, game = recorded()
    game[field] = value
    with pytest.raises(ValueError):
        reconstruct_game(deck, deck, game)


@pytest.mark.parametrize('mode,expected_exit', [('valid', 0), ('drift', 1), ('overwrite', 2), ('malformed', 2)])
def test_offline_cli_status_privacy_and_input_preservation(tmp_path, mode, expected_exit):
    from scripts.regression_matrix_replay import _write_deck_manifest
    deck, game = recorded()
    if mode == 'drift':
        game['log_hash'] = '0' * 64
    manifest = tmp_path / 'decks.json'
    trace = tmp_path / 'trace.json'
    output = trace if mode == 'overwrite' else tmp_path / 'report.json'
    _write_deck_manifest(str(manifest), [{'name': 'A', 'mainboard': deck}, {'name': 'B', 'mainboard': deck}],
                         {'source': 'canonical Island unit fixture; not competitive decks'})
    trace.write_text(json.dumps({'games': [] if mode == 'malformed' else [game]}))
    before = (manifest.read_bytes(), trace.read_bytes())
    completed = subprocess.run([sys.executable, str(Path(__file__).parents[1] / 'scripts/reconstruct_action_replay.py'),
        '--deck-manifest', str(manifest), '--trace', str(trace), '--output', str(output)],
        capture_output=True, text=True, timeout=30)
    assert completed.returncode == expected_exit, completed.stderr
    assert (manifest.read_bytes(), trace.read_bytes()) == before
    assert 'Island' not in completed.stdout
    if expected_exit in (0, 1):
        report = json.loads(output.read_text())
        assert report['matched'] is (expected_exit == 0)
        if mode == 'drift':
            assert report['first_divergence']['field'] == 'log_hash'


@pytest.mark.parametrize('mode,expected_exit', [('valid', 0), ('drift', 1), ('existing', 2), ('existing_report', 2),
    ('same_output', 2), ('input_alias', 2)])
def test_cli_private_decision_export_provenance_privacy_and_no_overwrite(tmp_path, mode, expected_exit):
    from scripts.regression_matrix_replay import _write_deck_manifest
    deck, game = recorded()
    if mode == 'drift':
        game['log_hash'] = '0' * 64
    manifest, trace, output, decisions = [tmp_path / name for name in ('decks.json', 'trace.json', 'report.json', 'decisions.jsonl')]
    _write_deck_manifest(str(manifest), [{'name': 'A', 'mainboard': deck}, {'name': 'B', 'mainboard': deck}],
                         {'source': 'canonical unit fixture; not a natural game'})
    games = [game, recorded(seed=938, starting_player=2)[1]] if mode == 'valid' else [game]
    trace.write_text(json.dumps({'games': games}))
    if mode == 'existing':
        decisions.write_text('preserve this evidence')
    if mode == 'existing_report':
        output.write_text('preserve this report')
    if mode == 'same_output':
        decisions = output
    if mode == 'input_alias':
        decisions.symlink_to(trace)
    before = (manifest.read_bytes(), trace.read_bytes())
    result = subprocess.run([sys.executable, str(Path(__file__).parents[1] / 'scripts/reconstruct_action_replay.py'),
        '--deck-manifest', str(manifest), '--trace', str(trace), '--output', str(output),
        '--decision-output', str(decisions)], capture_output=True, text=True, timeout=30)
    assert result.returncode == expected_exit, result.stderr
    assert (manifest.read_bytes(), trace.read_bytes()) == before
    assert 'Island' not in result.stdout
    if expected_exit in (0, 1):
        rows = [json.loads(line) for line in decisions.read_text().splitlines()]
        assert rows[0]['kind'] == 'private_reconstruction_start'
        assert rows[-1]['kind'] == 'private_reconstruction_end'
        assert rows[-1]['matched'] is (expected_exit == 0)
        states = [row for row in rows if row['kind'] == 'decision_state']
        assert len(states) == 80 * len(games)
        for index, recorded_game in enumerate(games):
            group = [row for row in states if row['game'] == index]
            assert len(group) == 80
            assert all(row['seed'] == recorded_game['seed'] and row['starting_player'] == recorded_game['starting_player'] for row in group)
            assert [row['decision'] for row in group] == list(range(80))
        assert all(len(states[0]['players'][str(seat)]['hand']) == 7 for seat in (1, 2))
        assert decisions.stat().st_mode & 0o777 == output.stat().st_mode & 0o777 == 0o600
    if mode == 'existing':
        assert decisions.read_text() == 'preserve this evidence'
    if mode == 'existing_report':
        assert output.read_text() == 'preserve this report'
    elif expected_exit == 2:
        assert not output.exists()
