"""Small canonical engine transitions; these are not pilot cells or run evidence."""
from copy import deepcopy
import importlib
import importlib.util
from types import SimpleNamespace

import pytest


def game():
    name = 'scripts.archetype_matrix_game'
    assert importlib.util.find_spec(name) is not None, 'Streamed game adapter is missing'
    return importlib.import_module(name)


def trace():
    from card_data.seed_cards import seed_card_payload
    rows = [{**seed_card_payload('Island'), 'card_name': 'Island', 'quantity': 60}]
    records = []
    outcome = game().play_game(rows, rows, seed=9933, game_id='unit-game',
        policy={'max_ticks': 2, 'max_turns': 100}, emit=records.append,
        choose=lambda state, moves, seat: SimpleNamespace(action={'type': 'keep_hand'}, reasoning='unit choice'))
    return records, outcome


def test_full_snapshot_rng_action_and_restart_replay():
    records, outcome = trace()
    assert outcome['status'] == 'tick_limit' and outcome['accepted_actions'] == 2
    assert [r['kind'] for r in records] == ['initial', 'action', 'action', 'final']
    assert 'rng_state' in records[0]['snapshot']
    assert records[1]['before']['pregame_pending'] is True
    assert records[1]['action'] == {'type': 'keep_hand', 'bottom_card_ids': []}
    assert records[1]['legal_moves'] and records[1]['reasoning'] == 'unit choice'
    assert game().replay_trace(iter(records)) == {'matched': True, 'actions': 2,
        'status': 'tick_limit', 'restart_roundtrips': 2}


@pytest.mark.parametrize('field', ['actor', 'action', 'legal_moves', 'before', 'after', 'initial', 'final', 'missing', 'extra'])
def test_first_divergence_cannot_be_hidden_by_rechaining(field):
    records, _ = trace()
    records = deepcopy(records)
    if field == 'actor': records[1]['actor'] = 2
    elif field == 'action': records[1]['action'] = {'type': 'invented'}
    elif field == 'legal_moves': records[1]['legal_moves'] = []
    elif field == 'before': records[1]['before']['players']['1']['life'] = 7
    elif field == 'after': records[1]['after']['rng_state'][1][0] = 17
    elif field == 'initial': records[0]['snapshot']['players']['1']['life'] = 1
    elif field == 'final': records[-1]['outcome']['accepted_actions'] = 99
    elif field == 'missing': records.pop()
    else: records.append(deepcopy(records[-1]))
    with pytest.raises(game().TraceDivergence) as raised:
        game().replay_trace(iter(records))
    assert type(raised.value.step) is int and raised.value.fields
    assert '9933' not in str(raised.value) and 'Island' not in str(raised.value)


def test_rejected_agent_action_is_error_not_pass_or_retry():
    from card_data.seed_cards import seed_card_payload
    rows = [{**seed_card_payload('Island'), 'card_name': 'Island', 'quantity': 60}]
    records, calls = [], []
    def bad(state, moves, seat):
        calls.append(seat)
        return SimpleNamespace(action={'type': 'play_land', 'card_id': 'missing'}, reasoning='invalid')
    outcome = game().play_game(rows, rows, seed=9934, game_id='unit-bad',
        policy={'max_ticks': 2, 'max_turns': 100}, emit=records.append, choose=bad)
    assert outcome['status'] == 'error' and outcome['accepted_actions'] == 0
    assert calls == [1] and outcome['winner'] is None
    assert records[-1]['kind'] == 'final'


def test_real_master_decision_can_feed_one_checked_transition():
    from card_data.seed_cards import seed_card_payload
    rows = [{**seed_card_payload('Island'), 'card_name': 'Island', 'quantity': 60}]
    records = []
    outcome = game().play_game(rows, rows, seed=9935, game_id='unit-real-master',
        policy={'max_ticks': 1, 'max_turns': 100}, emit=records.append)
    assert outcome['accepted_actions'] == 1 and outcome['status'] == 'tick_limit'
    assert records[1]['action']['type'] in {'keep_hand', 'mulligan'}
    assert game().replay_trace(iter(records))['matched'] is True


def test_canonical_nine_decks_and_physical_seat_swap():
    from scripts.archetype_matrix_plan import build_plan
    from pathlib import Path
    plan = build_plan('a'*40, (Path(__file__).parents[1]/'decks/builtin_decks.py').read_text())
    admitted = game().admit_decks(plan)
    assert set(admitted) == set(plan['decks']) and len(admitted) == 9
    assert all(sum(r['quantity'] for r in rows) >= 60 for rows in admitted.values())
    cell = plan['cells'][0]
    one = game().cell_decks(admitted, cell)
    two = game().cell_decks(admitted, {**cell, 'deck_a_seat': 2})
    assert one == two[::-1]


def test_early_final_is_not_a_valid_tick_limit_even_if_self_consistent():
    records, _ = trace()
    final = deepcopy(records[-1])
    final['snapshot'] = records[1]['after']
    final['outcome']['accepted_actions'] = 1
    with pytest.raises(game().TraceDivergence):
        game().replay_trace(iter([records[0], records[1], final]))


def test_replay_reconstructs_full_unit_trace_in_fresh_python_process(tmp_path):
    import json
    import os
    from pathlib import Path
    import subprocess
    import sys
    records, _ = trace()
    path = tmp_path/'unit-trace.jsonl'
    path.write_text(''.join(json.dumps(row)+'\n' for row in records))
    code = '''import json,sys
from scripts.archetype_matrix_game import replay_trace
with open(sys.argv[1]) as stream:
 print(json.dumps(replay_trace(json.loads(line) for line in stream)))
'''
    result = subprocess.run([sys.executable, '-B', '-c', code, str(path)],
        cwd=Path(__file__).parents[1], env={**os.environ, 'PYTHONHASHSEED': '0'},
        text=True, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'matched': True, 'actions': 2,
        'status': 'tick_limit', 'restart_roundtrips': 2}
