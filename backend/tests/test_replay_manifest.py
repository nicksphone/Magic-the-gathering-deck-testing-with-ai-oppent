"""Pinned resolved inputs are reproducibility evidence, not rules certification."""
import json
from copy import deepcopy

import pytest

from scripts import regression_matrix_replay as replay


def decks():
    return [{'name': name, 'mainboard': [{'quantity': 60, 'card_name': 'Island',
             'type_line': 'Basic Land - Island', 'mana_cost': '', 'oracle_text': '{T}: Add {U}.'} ]}
            for name in ['First', 'Second', 'Third']]


def manifest(tmp_path):
    path = tmp_path / 'decks.json'
    replay._write_deck_manifest(str(path), decks(), {'fixture': True, 'not_a_competitive_deck': True})
    return path


def test_round_trip_keeps_order_metadata_and_records_selected_hash(tmp_path):
    path = manifest(tmp_path)
    selected, provenance = replay._load_deck_manifest(str(path), 2)
    assert selected == decks()[:2]
    assert provenance['input_source'] == 'resolved_manifest'
    assert provenance['corpus_sha256'] == replay._corpus_hash(selected)
    assert provenance['source_corpus_sha256'] == replay._corpus_hash(decks())
    assert provenance['source_provenance']['fixture'] is True


def test_hash_does_not_depend_on_json_whitespace_but_file_hash_does(tmp_path):
    path = manifest(tmp_path)
    _, before = replay._load_deck_manifest(str(path), 3)
    path.write_text(json.dumps(json.loads(path.read_text()), sort_keys=True))
    _, after = replay._load_deck_manifest(str(path), 3)
    assert before['corpus_sha256'] == after['corpus_sha256']
    assert before['manifest_sha256'] != after['manifest_sha256']


@pytest.mark.parametrize('field,value', [('quantity', 0), ('quantity', -1), ('quantity', True),
    ('quantity', 251), ('quantity', '60'), ('card_name', ''), ('oracle_text', None),
    ('mana_cost', None), ('type_line', ''), ('types', ['']), ('types', ['Land'])])
def test_malformed_resolved_card_is_rejected(tmp_path, field, value):
    path = manifest(tmp_path)
    data = json.loads(path.read_text())
    if field == 'types':
        data['decks'][0]['mainboard'][0].pop('type_line')
    data['decks'][0]['mainboard'][0][field] = value
    data['corpus_sha256'] = replay._corpus_hash(data['decks'])
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        replay._load_deck_manifest(str(path), 2)


@pytest.mark.parametrize('kind', ['version', 'bool_version', 'missing_hash', 'duplicate', 'too_few',
                                  'oversized', 'unselected_bad_card', 'tamper', 'missing_quantity'])
def test_manifest_integrity_and_all_deck_validation(tmp_path, kind):
    path = manifest(tmp_path)
    data = json.loads(path.read_text())
    if kind == 'version':
        data['schema_version'] = 2
    elif kind == 'bool_version':
        data['schema_version'] = True
    elif kind == 'missing_hash':
        data.pop('corpus_sha256')
    elif kind == 'duplicate':
        data['decks'][1]['name'] = data['decks'][0]['name']
    elif kind == 'too_few':
        data['decks'] = data['decks'][:1]
    elif kind == 'oversized':
        data['decks'][0]['mainboard'] = [deepcopy(data['decks'][0]['mainboard'][0]) for _ in range(5)]
    elif kind == 'unselected_bad_card':
        data['decks'][2]['mainboard'][0]['quantity'] = -1
    elif kind == 'missing_quantity':
        data['decks'][0]['mainboard'][0].pop('quantity')
    else:
        data['decks'][0]['mainboard'][0]['oracle_text'] = 'Changed data'
    if kind not in {'tamper', 'missing_hash'}:
        data['corpus_sha256'] = replay._corpus_hash(data['decks'])
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        replay._load_deck_manifest(str(path), 2)


def test_cli_manifest_path_does_not_bootstrap_or_hydrate_database(tmp_path, monkeypatch):
    path = manifest(tmp_path)
    output = tmp_path / 'results.json'
    export = tmp_path / 'selected.json'
    for method in ['init_db', 'Session', 'hydrate_deck_cards', 'ensure_builtin_decks', 'ensure_expansion_top_decks']:
        monkeypatch.setattr(replay, method, lambda *a, **k: pytest.fail('manifest path touched mutable database'))
    def match(*args):
        return {'winner': 1, 'turns': 3, 'games_played': 1, 'wins': {'deck_a': 1, 'deck_b': 0},
                'timeout': False, 'log': [], 'games': [{'seed': args[2], 'starting_player': 1, 'play_draw_chooser': 1}]}
    monkeypatch.setattr(replay, 'run_match', match)
    monkeypatch.setattr('sys.argv', ['replay', '--deck-manifest', str(path), '--max-decks', '2',
                       '--matches-per-pair', '1', '--write-deck-manifest', str(export), '--output', str(output)])
    replay.main()
    result = json.loads(output.read_text())
    assert result['matches'] == 2 and result['determinism_failures'] == 0
    assert result['input_provenance']['corpus_sha256'] == replay._corpus_hash(decks()[:2])
    assert replay._load_deck_manifest(str(export), 2)[0] == decks()[:2]


def test_cli_rejects_bad_manifest_before_simulation(tmp_path, monkeypatch):
    path = manifest(tmp_path)
    path.write_text('{}')
    monkeypatch.setattr(replay, 'run_match', lambda *a: pytest.fail('invalid manifest ran a game'))
    monkeypatch.setattr('sys.argv', ['replay', '--deck-manifest', str(path)])
    with pytest.raises(SystemExit) as error:
        replay.main()
    assert error.value.code == 2
