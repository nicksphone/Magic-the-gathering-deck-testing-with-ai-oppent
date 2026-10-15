"""Explicit fixture-event pipeline controls; no games or learned artifact promotion."""
from copy import deepcopy
import json

import pytest

from ai.log_priors import _opponent_archetype
from scripts.build_ai_log_priors import _qualified_export_contexts
from scripts.extract_training_examples import _feature_row, extract_examples_from_games_jsonl


def event(context='Aggro', index=0, turn=2, **extra):
    return dict(pid=1, turn=turn, hand=['Fixture spell'],
                action={'type': 'cast_spell', 'card_name': 'Fixture spell'},
                opponent_archetype=context, action_index=index, **extra)


def write_exports(root, *, raw_logs=True):
    root.mkdir()
    lines = []
    for index, (context, turn) in enumerate([('Aggro', 2)] * 3 + [('Control', 9)] * 3):
        lines.extend(('AI TRACE ' + json.dumps(event(context, index, turn)),
                      'Player A casts/activates Fixture spell.'))
    path = root / 'games.jsonl'
    path.write_text(json.dumps({'game': 7, 'log': lines}) + '\n')
    examples = extract_examples_from_games_jsonl(path)
    (root / 'training_examples.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in examples))
    if not raw_logs:
        path.unlink()
    return examples


def test_real_extraction_to_existing_reconciler_retains_context(tmp_path):
    root = tmp_path / 'examples-only'
    rows = write_exports(root, raw_logs=False)
    payload, unavailable = _qualified_export_contexts(root)
    assert unavailable == {}
    assert [r['action_index'] for r in rows] == list(range(6))
    contexts = payload['cards']['fixture spell']['opponent_archetypes']
    assert set(contexts) == {'aggro', 'control'}
    assert contexts['aggro']['casts'] == contexts['control']['casts'] == 3
    assert contexts['aggro']['avg_turn'] == 2.0
    assert contexts['control']['avg_turn'] == 9.0


def test_raw_and_extracted_events_deduplicate_without_mutation(tmp_path):
    root = tmp_path / 'both'
    write_exports(root)
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    payload, unavailable = _qualified_export_contexts(root)
    assert unavailable == {}
    assert payload['cards']['fixture spell']['casts'] == 6
    assert payload['cards']['fixture spell']['opponent_archetypes']['aggro']['casts'] == 3
    assert {p.name: p.read_bytes() for p in root.iterdir()} == before


@pytest.mark.parametrize('labels', [
    {'opp_archetype': ' AGGRO '}, {'opponent_archetype': 'Aggro'},
    {'opp_archetype': 'Aggro', 'opponent_archetype': ' aggro '},
    {'opp_archetype': None, 'opponent_archetype': 'Aggro'},
    {'opp_archetype': 'Aggro', 'opponent_archetype': None},
])
def test_alias_normalization_matches_existing_semantics(labels):
    trace = event()
    trace.pop('opponent_archetype')
    trace.update(labels)
    before = deepcopy(trace)
    row = _feature_row({'game': 7}, trace)
    assert row['opponent_archetype'] == _opponent_archetype(trace) == 'aggro'
    assert 'opp_archetype' not in row
    assert trace == before


@pytest.mark.parametrize('labels', [
    {}, {'opp_archetype': None}, {'opponent_archetype': 'unknown'},
    {'opponent_archetype': 'unlisted'}, {'opponent_archetype': True},
    {'opponent_archetype': []}, {'opponent_archetype': {}},
    {'opp_archetype': 'Aggro', 'opponent_archetype': 'Control'},
    {'opp_archetype': 'Aggro', 'opponent_archetype': 'unknown'},
])
def test_absent_invalid_or_conflicting_context_is_unavailable(labels):
    trace = event()
    trace.pop('opponent_archetype')
    trace.update(labels)
    before = deepcopy(trace)
    row = _feature_row({'game': 7, 'opponent_archetype': 'Aggro'}, trace)
    assert _opponent_archetype(trace) is None
    assert 'opponent_archetype' not in row and 'opp_archetype' not in row
    assert trace == before


@pytest.mark.parametrize('index', [0, 1, 2**80])
def test_explicit_nonnegative_integer_index_has_no_new_cap(index):
    row = _feature_row({'game': 7}, event(index=index))
    assert type(row['action_index']) is int and row['action_index'] == index


@pytest.mark.parametrize('index', [None, True, False, -1, '0', 0.0, [], {}])
def test_invalid_action_index_is_omitted(index):
    row = _feature_row({'game': 7}, event(index=index))
    assert 'action_index' not in row
    assert row['opponent_archetype'] == 'aggro'


def test_unlabeled_unindexed_row_is_whole_legacy_equal_and_no_inference():
    trace = event()
    trace.pop('opponent_archetype'); trace.pop('action_index')
    trace.update(opp_battlefield=[{'types': ['Creature'], 'name': 'Private name'}],
                 opponent_deck='Aggro', teacher_config={'opponent_archetype': 'Aggro'},
                 arbitrary_secret='do-not-promote')
    game = {'game': 7, 'opponent_archetype': 'Aggro', 'action_index': 9}
    before = deepcopy((game, trace))
    expected = {
        'game': 7, 'winner': None, 'pid': 1, 'turn': 2, 'step': None,
        'active_player': None, 'priority_player': None,
        'hand': ['Fixture spell'], 'hand_size': 1, 'opp_hand': [], 'opp_hand_size': 0,
        'battlefield': [], 'opp_battlefield': [{'types': ['Creature'], 'name': 'Private name'}],
        'graveyard_count': 0, 'opp_graveyard_count': 0, 'library_count': 0, 'opp_library_count': 0,
        'life': {'self': None, 'opp': None}, 'mana_pool': {}, 'legal_non_pass': False,
        'legal_action_types': [], 'legal_has_land': False, 'board_role_hint': 'normal',
        'board_snapshot': {
            'battlefield_count': 0, 'opp_battlefield_count': 1, 'hand_count': 1, 'opp_hand_count': 0,
            'battlefield_tapped': 0, 'opp_battlefield_tapped': 0,
            'graveyard_count': 0, 'opp_graveyard_count': 0, 'library_count': 0, 'opp_library_count': 0,
            'battlefield_types': {}, 'opp_battlefield_types': {'Creature': 1},
        },
        'action_type': 'cast_spell', 'action_card_name': 'Fixture spell',
        'selected_face_index': None, 'reasoning': '', 'reason_code': 'unknown',
    }
    assert _feature_row(game, trace) == expected
    assert (game, trace) == before
    assert 'arbitrary_secret' not in _feature_row(game, trace)


def test_context_without_index_remains_unqualified(tmp_path):
    root = tmp_path / 'missing-index'; root.mkdir()
    trace = event(); trace.pop('action_index')
    row = _feature_row({'game': 7}, trace)
    (root / 'training_examples.jsonl').write_text(json.dumps(row) + '\n')
    payload, unavailable = _qualified_export_contexts(root)
    assert payload['cards'] == {}
    assert unavailable == {'missing_action_provenance': 1}
