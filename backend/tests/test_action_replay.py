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
