"""Public provenance/count protocols, NOT native games or training evidence."""
import json

from scripts.build_ai_log_priors import _qualified_export_contexts


def _example(game, index=0, turn=2):
    return {'game': game, 'action_index': index, 'pid': 1, 'turn': turn,
            'action_type': 'cast_spell', 'action_card_name': 'Llanowar Elves',
            'opponent_archetype': 'control'}


def _write_examples(folder, rows):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'training_examples.jsonl').write_text(
        ''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')


def test_raw_and_example_copies_of_one_game_action_count_once(tmp_path):
    _write_examples(tmp_path, [_example('game-01.json')] * 3)
    trace = {'trace': True, 'action_index': 0, 'pid': 1, 'turn': 2,
             'player_name': 'Player A', 'opponent_archetype': 'control',
             'action': {'type': 'cast_spell', 'card_name': 'Llanowar Elves'}}
    protocol = {'game': 'game-01.json', 'log': [
        'AI TRACE ' + json.dumps(trace), 'Player A casts/activates Llanowar Elves.']}
    (tmp_path / 'games.jsonl').write_text(json.dumps(protocol) + '\n', encoding='utf-8')
    payload, unavailable = _qualified_export_contexts(tmp_path)
    assert unavailable == {}
    assert payload['samples'] == {'games': 1, 'logs': 1}
    assert payload['cards'] == {}


def test_same_typed_game_in_distinct_series_counts_both(tmp_path):
    for series in ('series-00000', 'series-00001'):
        _write_examples(tmp_path / series, [_example('game-01.json')])
    payload, unavailable = _qualified_export_contexts(tmp_path)
    assert unavailable == {}
    assert payload['samples'] == {'games': 2, 'logs': 2}
    assert payload['cards'] == {}


def test_integer_and_string_game_identifiers_stay_distinct(tmp_path):
    _write_examples(tmp_path, [_example(1), _example('1')])
    payload, unavailable = _qualified_export_contexts(tmp_path)
    assert unavailable == {}
    assert payload['samples'] == {'games': 2, 'logs': 2}
    assert payload['cards'] == {}


def test_conflicting_only_action_does_not_count_a_game(tmp_path):
    _write_examples(tmp_path, [_example('game-01.json'), _example('game-01.json', turn=3)])
    payload, unavailable = _qualified_export_contexts(tmp_path)
    assert unavailable == {'conflicting_action_provenance': 2}
    assert payload['samples'] == {'games': 0, 'logs': 0}
    assert payload['cards'] == {}


def test_unconflicted_action_counts_game_despite_other_conflicted_action(tmp_path):
    _write_examples(tmp_path, [_example('game-01.json'),
                               _example('game-01.json', turn=3),
                               _example('game-01.json', index=1)])
    payload, unavailable = _qualified_export_contexts(tmp_path)
    assert unavailable == {'conflicting_action_provenance': 2}
    assert payload['samples'] == {'games': 1, 'logs': 1}
    assert payload['cards'] == {}


def test_multiple_accepted_actions_count_one_actual_game(tmp_path):
    _write_examples(tmp_path, [_example('game-01.json'), _example('game-01.json', index=1)])
    payload, unavailable = _qualified_export_contexts(tmp_path)
    assert unavailable == {}
    assert payload['samples'] == {'games': 1, 'logs': 2}
    assert payload['cards'] == {}
