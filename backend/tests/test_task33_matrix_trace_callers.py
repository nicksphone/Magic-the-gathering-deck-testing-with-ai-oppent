"""Caller protocols, NOT played games, native outcomes or export admission.

Actual outer callers, real BO3 seat policy, real source hashing and the real
context factory run. Games, payloads, partition/callable checks and packaging
are explicit public doubles. Boards reuse complete seed data, never retags.
"""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace

import pytest

from ai import deck_analysis
from analytics import decision_quality
from analytics.resource_budget import RESOURCE_LIMITS
from card_data.seed_cards import seed_card_payload
from scripts import baseline_report
from scripts import matchup_round_robin as runner
from scripts import regression_matrix_replay as replay
from scripts.oracle_corpus_report import collect_corpus


def _canonical_roster():
    rows = []
    for name, text in runner.builtin_templates().items():
        boards = {key: [{**deepcopy(seed_card_payload(card)),
                         'card_name': seed_card_payload(card)['name'], 'quantity': count}
                        for card, count in inventory.items()]
                  for key, inventory in runner._template_inventory(text).items()}
        # Stale export labels must not replace the actual effective configuration.
        rows.append(dict(source='builtin', id=None, name=name,
                         classification_status='resolved', archetype='Tribal', **boards))
    return sorted(rows, key=lambda row: row['name'])


@pytest.mark.parametrize('route', ['fixed', 'bo3'])
@pytest.mark.parametrize('case', [
    'known', 'unknown-one', 'unknown-two', 'unresolved-row', 'foreign-label', 'empty-label',
])
def test_actual_matrix_callers_bind_physical_opponents_or_keep_legacy(tmp_path, monkeypatch, route, case):
    rows = _canonical_roster()
    left, right = rows[:2]
    labels = {left['name']: 'Aggro', right['name']: 'Control'}
    if case == 'unknown-one': labels[left['name']] = 'unknown'
    if case == 'unknown-two': labels[right['name']] = 'unknown'
    if case == 'unresolved-row': left['classification_status'] = 'unknown'
    if case == 'foreign-label': labels[left['name']] = 'Unlisted public label'
    if case == 'empty-label': labels[right['name']] = ''
    qualify = case == 'known'
    corpus = collect_corpus()
    export = runner.make_export(rows, corpus_sha256=runner.digest(corpus))
    original_export = deepcopy(export)
    scheduled = runner.build_schedule(rows, [7])[:2]
    assert len(scheduled) == 2
    # Two genuine coordinates for this protocol, not a production roster change.
    def schedule(supplied, tokens):
        assert runner.canonical_bytes(supplied) == runner.canonical_bytes(rows) and tokens == [7]
        return deepcopy(scheduled)
    monkeypatch.setattr(runner, 'build_schedule', schedule)
    by_board = {runner.digest(row['mainboard']): row['name'] for row in rows}
    for row in (left, right):
        assert by_board[runner.digest(row['mainboard'])] == row['name']
    guesses, factories, calls, payloads, source_checks = [], [], [], [], []
    def guess(board):
        name = by_board[runner.digest(board)]
        guesses.append(name)
        return labels.get(name, 'Tokens')
    monkeypatch.setattr(deck_analysis, 'guess_archetype', guess)
    native_factory = replay.contextual_trace
    def factory(builder, opponent_archetypes):
        factories.append(deepcopy(opponent_archetypes))
        return native_factory(builder, opponent_archetypes)
    monkeypatch.setattr(replay, 'contextual_trace', factory)
    def public_trace(state, pid, legal, action, reasoning, **options):
        assert legal is state.public_legal and action is state.public_action
        assert reasoning == 'caller protocol only'
        assert options == {'knowledge_usage': {'public-protocol': True}}
        payload = dict(trace=True, pid=pid, turn=state.turn, action=deepcopy(action),
                       stall_actionable_options=False, legal_has_land=False)
        payloads.append(deepcopy(payload))
        return payload
    monkeypatch.setattr(decision_quality, 'build_trace_payload', public_trace)
    def verify_callable(function, relative, binding, backend):
        source_checks.append((function, relative))
    monkeypatch.setattr(runner, 'verify_measurement_callable', verify_callable)
    monkeypatch.setattr(runner, 'verify_measurement_partition', lambda *args: dict(protocol_only=True))
    monkeypatch.setattr(runner, 'measurement_runtime_identity', lambda: dict(protocol_only=True))
    monkeypatch.setattr(baseline_report, 'package_measurement', lambda *args, **kwargs: dict(protocol_only=True))
    def game(one, two, seed, level, ticks, **options):
        names = [by_board[runner.digest(board)] for board in (one, two)]
        trace, observed = options['trace_builder'], []
        for pid in (1, 2):
            action = {'type': 'pass_priority'}
            legal = [action]
            state = SimpleNamespace(turn=1, public_action=action, public_legal=legal,
                players={1: SimpleNamespace(name='Player A'), 2: SimpleNamespace(name='Player B')})
            decision = SimpleNamespace(reasoning='caller protocol only', knowledge_usage={'public-protocol': True})
            payload = trace(state, pid, legal, action, decision)
            binder = getattr(trace, 'bind_native_action', None)
            if binder is not None:
                payload = binder(payload, state, pid, action, 0)
            observed.append(dict(pid=pid, binder=binder, payload=deepcopy(payload),
                                 original=deepcopy(payloads[-1])))
        calls.append(dict(names=names, seed=seed, options=options, payloads=observed))
        raw = ['AI TRACE ' + json.dumps(row['payload']) for row in observed]
        options['budget'].begin_game(raw)
        result = dict(winner=1, turn=1, ticks=2, timeout=False, log=list(raw),
            log_hash=hashlib.sha256('\n'.join(raw).encode()).hexdigest(), starting_player=options['starting_player'])
        replay._record_game_evidence(result, raw, options['record_game'])
        return result
    monkeypatch.setattr(replay, 'run_game', game)
    files = runner.collect_source_manifest(runner.BACKEND)
    binding = dict(schema_version=1, source_base_commit='a' * 40,
                   backend_files=files, backend_sha256=runner.digest(files))
    directory = tmp_path / route
    if route == 'fixed':
        cards = [dict(value, cached=True, status='structured_effect') for value in corpus.values()]
        oracle = tmp_path / 'oracle.json'
        oracle.write_text(json.dumps(dict(cards=cards, status_unique={'structured_effect': len(cards)},
            status_weighted={'structured_effect': sum(card['copies'] for card in cards)})))
        def charge(path, count):
            assert not path.exists() and type(count) is int and count > 0
        output = runner.run_fixed_game_measurement(export, [7], selected_pair=[left['name'], right['name']],
            selected_token=7, difficulty='master', max_ticks=2, limits=dict(RESOURCE_LIMITS),
            private_directory=directory, source_binding=binding, partition={'arm': 'protocol'},
            partition_sha256='0' * 64, activation_check=None, artifact_guard=charge,
            oracle_path=oracle, log_priors_path=runner.BACKEND / 'ai/data/log_priors.json')
        configuration = output['production']['configuration']
        assert output['production']['attempted_games'] == 2
        assert output['production']['source']['equal'] is True
        assert [call['options']['starting_player'] for call in calls] == [1, 1]
    else:
        output = runner.run_round_robin(export, [7], difficulty='master', max_ticks=2,
            limits=dict(RESOURCE_LIMITS), private_directory=directory, source_binding=binding)
        configuration = output['manifest']
        assert output['attempted_series'] == 2 and output['complete'] is True
        assert output['measured_source']['equal'] is True
        assert [call['options']['starting_player'] for call in calls] == [1, 2, 1, 2]
    expected_pairs = [[left['name'], right['name']], [right['name'], left['name']]]
    expected_names = expected_pairs if route == 'fixed' else [pair for pair in expected_pairs for _ in range(2)]
    assert [call['names'] for call in calls] == expected_names
    assert export == original_export
    for call in calls:
        for row in call['payloads']:
            pid, payload = row['pid'], row['payload']
            if qualify:
                assert callable(row['binder']), 'Actual matrix caller did not bind contextual_trace'
                assert payload['opponent_archetype'] == labels[call['names'][2-pid]].lower()
                assert payload['pid'] == pid and payload['action_index'] == 0
                assert payload['player_name'] == {1: 'Player A', 2: 'Player B'}[pid]
            else:
                assert row['binder'] is None, 'Unknown classification must retain the legacy builder'
                assert payload == row['original']
                assert 'opponent_archetype' not in payload and 'opp_archetype' not in payload
                assert 'action_index' not in payload and 'card_name' not in payload['action']
    if qualify:
        assert factories == [{1: 'Control', 2: 'Aggro'}, {1: 'Aggro', 2: 'Control'}]
        assert any(fn is factory and path == 'scripts/regression_matrix_replay.py' for fn, path in source_checks)
    else:
        assert factories == []
    effective = configuration['effective_archetypes']
    for row in rows:
        if route == 'bo3' and row['classification_status'] != 'resolved':
            assert row['name'] not in effective, 'No newly guessed label for unresolved rows'
            assert row['name'] not in guesses
        else:
            assert effective[row['name']] == labels.get(row['name'], 'Tokens')
    assert all(row['archetype'] == 'Tribal' for row in original_export['decks'])
