"""Authored-only producer controls, not experiments, completed games or learning.

Complete public RAW enters Factory before capture. The control chooser selects
native legal actions; it is not the AI under evaluation. Fault injections and
the in-memory receipt sink are protocol controls, not durable game evidence.
"""
from copy import deepcopy
import hashlib
from itertools import groupby
import json
from pathlib import Path
import random
from types import SimpleNamespace

import pytest

from analytics.resource_budget import RESOURCE_LIMITS, ResourceBudget, SimulationResourceLimit
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory
from rules_engine.action_validation import ActionRejected
from scripts import regression_matrix_replay as replay
from scripts.build_ai_log_priors import _qualified_export_contexts
from scripts.extract_training_examples import extract_examples_from_games_jsonl


FIXTURES = Path(__file__).parent / 'fixtures/knowledge_profiles'
SEED_SHA = '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
PROVENANCE_SHA = 'f15047f1ecb06fdaa985a58537d01b6497683637d7caf88db518dea469fc1ca2'
OMITTED = object()
CONTEXTS = {1: 'Control', 2: 'Aggro'}  # Opponent label FOR the physical actor.
NATIVE_FACTORY = MatchFactory.from_decks
NATIVE_CHECKED = replay.checked_action


def _contextual_trace(builder, labels):
    factory = getattr(replay, 'contextual_trace', None)
    assert callable(factory), 'Missing Task 3.3 native trace context adapter'
    return factory(builder, labels)


def _public_decks(seed):
    body = (FIXTURES / 'seed155-scryfall.jsonl').read_bytes()
    assert hashlib.sha256(body).hexdigest() == SEED_SHA
    provenance = (FIXTURES / 'PROVENANCE.json').read_bytes()
    assert hashlib.sha256(provenance).hexdigest() == PROVENANCE_SHA
    assert json.loads(provenance)['snapshot_sha256'] == SEED_SHA
    raw = {row['name']: row for row in map(json.loads, body.splitlines())}
    rng = random.Random(seed)
    decks = []
    for _ in (1, 2):
        order = list(range(60))
        rng.shuffle(order)
        names = ['Forest'] * 60
        # Same seed and genuine Factory shuffle; make the named source a born
        # opening-hand card through INPUT layout, never by post-capture repair.
        names[order[-1]] = 'Llanowar Elves'
        decks.append([{**deepcopy(raw[name]), 'card_name': name,
                       'quantity': sum(1 for _ in copies),
                       'image_uri': raw[name]['image_uris']['normal']}
                      for name, copies in groupby(names)])
    return decks, {name: raw[name] for name in ('Forest', 'Llanowar Elves')}


def _trace(state, pid, legal, action, decision):
    # Deliberately minimal public producer fixture, not a private-state export.
    def board(owner):
        return [{'name': state.cards[cid].name, 'types': list(state.cards[cid].types),
                 'tapped': state.cards[cid].tapped}
                for cid in state.players[owner].battlefield]
    return {'trace': True, 'pid': pid, 'turn': state.turn, 'step': str(state.step),
            'action': deepcopy(action),
            'legal_non_pass': any(move.get('type') != 'pass_priority' for move in legal),
            'battlefield': board(pid), 'opp_battlefield': board(3 - pid),
            'life': {'self': state.players[pid].life, 'opp': state.players[3 - pid].life}}


class ObservedBudget(ResourceBudget):
    """Forward native accounting; one optional explicitly injected refusal."""

    def __init__(self, refuse_at=None):
        super().__init__()
        self.refuse_at = refuse_at
        self.commits = 0
        self.payloads = []

    def trace_line(self, payload):
        self.payloads.append(deepcopy(payload))
        return super().trace_line(payload)

    def accept_candidate(self, previous, candidate, trace_line=None):
        if self.refuse_at == self.commits:
            raise SimulationResourceLimit('game_log')
        result = super().accept_candidate(previous, candidate, trace_line)
        self.commits += 1
        return result


def _run(monkeypatch, *, seat=1, labels=CONTEXTS, seed=731, builder=_trace,
         reject_after=None, budget=None, names=('Player A', 'Player B'), receipt=True):
    decks, raw = _public_decks(seed)
    before_decks = deepcopy(decks)
    observed = SimpleNamespace(births=[], checked=[], configurations=[],
                               callback_payloads=[], raw=None, result=None)

    def born(left, right, **options):
        state = NATIVE_FACTORY(left, right, names[0], names[1],
                               game_id='task33-public-unit', **options)
        for pid in (1, 2):
            assert sum(state.cards[cid].name == 'Llanowar Elves'
                       for cid in state.players[pid].hand) == 1
        for card in state.cards.values():
            expected = raw[card.name]
            assert card.oracle_text == expected['oracle_text']
            assert card.type_line == expected['type_line']
            assert card.mana_cost == expected['mana_cost']
            expected_types = ['Land'] if card.name == 'Forest' else ['Creature']
            assert card.types == expected_types and card.keywords == []
            for key in ('physical', 'values'):
                facts = card.characteristic_record[key]
                assert facts['name'] == expected['name']
                assert facts['oracle_text'] == expected['oracle_text']
                assert facts['type_line'] == expected['type_line']
                assert facts['mana_cost'] == expected['mana_cost']
                assert facts['types'] == expected_types and facts['keywords'] == []
        observed.births.append(serialize_match_snapshot(state))
        return state

    class PublicControlChooser:
        def __init__(self, **configuration):
            observed.configurations.append(deepcopy(configuration))

        def choose_action(self, state, moves, pid):
            for kind in ('keep_hand', 'cast_spell', 'play_land', 'pass_priority'):
                candidates = [move for move in moves if move.get('type') == kind]
                if candidates:
                    return SimpleNamespace(action=deepcopy(candidates[0]),
                                           reasoning='public unit control')
            raise AssertionError('Public fixture requires an unplanned action kind')

    def checked(state, engine, pid, action):
        if reject_after == len(observed.checked):
            raise ActionRejected('Explicit public unit rejection')
        before = serialize_match_snapshot(state)
        candidate = NATIVE_CHECKED(state, engine, pid, action)
        assert serialize_match_snapshot(state) == before
        observed.checked.append((pid, deepcopy(action),
                                 deepcopy(candidate.starting_decks),
                                 deepcopy(candidate.sideboard_facts['inventory'])))
        return candidate

    def build(state, pid, moves, action, decision):
        payload = builder(state, pid, moves, action, decision)
        observed.callback_payloads.append((payload, deepcopy(payload)))
        return payload

    def record(result, raw_log):
        # Unit-only in-memory receipt, never passed off as a durable artifact.
        observed.raw = list(raw_log)
        encoded = json.dumps(raw_log, ensure_ascii=True, separators=(',', ':'),
                             allow_nan=False).encode('utf-8')
        return {'complete': True, 'bytes': len(encoded),
                'raw_sha256': hashlib.sha256(encoded).hexdigest(),
                'reference': 'game-01.json'}

    selected_builder = build if builder is not None else None
    if labels is not OMITTED and labels is not None:
        selected_builder = _contextual_trace(selected_builder, deepcopy(labels))
    options = dict(starting_player=seat, trace_builder=selected_builder, budget=budget,
                   record_game=record if receipt else None)
    with monkeypatch.context() as patch:
        patch.setattr(replay, 'MatchFactory', SimpleNamespace(from_decks=born))
        patch.setattr(replay, 'AIAgent', PublicControlChooser)
        patch.setattr(replay, 'checked_action', checked)
        observed.result = replay.run_game(*decks, seed, 'strong', 16, **options)
    if not receipt:
        observed.raw = list(observed.result['log'])
    assert decks == before_decks
    if observed.births:
        inventory = observed.births[0]['sideboard_facts']['inventory']
        for _, _, starting_decks, actual_inventory in observed.checked:
            assert starting_decks == {1: before_decks[0], 2: before_decks[1]}
            assert actual_inventory == inventory
    assert all(payload == before for payload, before in observed.callback_payloads)
    return observed


def _rows(observed):
    return [json.loads(line[len('AI TRACE '):]) for line in observed.raw
            if line.startswith('AI TRACE ')]


@pytest.mark.parametrize('seat', [1, 2], ids=['seat1', 'seat2'])
def test_actual_native_prefix_has_bound_context_and_accepted_identity(monkeypatch, seat):
    observed = _run(monkeypatch, seat=seat)
    rows = _rows(observed)
    assert rows and len(rows) == observed.result['ticks'] == len(observed.checked)
    assert [row['action_index'] for row in rows] == list(range(len(rows)))
    assert observed.result.get('stop_reason') is None
    assert observed.result['winner'] is None  # Bounded episode, not a finished game.
    assert any(row['pid'] == seat and row['action']['type'] == 'cast_spell' for row in rows)
    for row, (pid, action, _, _) in zip(rows, observed.checked):
        assert type(row['action_index']) is int and row['pid'] == pid
        assert row['opponent_archetype'] == CONTEXTS[pid].lower()
        assert row['player_name'] == {1: 'Player A', 2: 'Player B'}[pid]
        assert {key: value for key, value in row['action'].items()
                if key != 'card_name'} == action
        if action['type'] == 'cast_spell':
            assert row['action']['card_name'] == 'Llanowar Elves'
        assert not {'hand', 'opp_hand', 'deck', 'snapshot', 'private_state'} & set(row)


def test_omitted_and_none_leave_whole_legacy_result_and_agent_config_equal(monkeypatch):
    # The genuine default non-receipt route has no elapsed-time result field.
    omitted = _run(monkeypatch, labels=OMITTED, receipt=False)
    explicit = _run(monkeypatch, labels=None, receipt=False)
    assert omitted.result == explicit.result and omitted.raw == explicit.raw
    assert omitted.configurations == explicit.configurations
    assert all('action_index' not in row and 'opponent_archetype' not in row
               and 'player_name' not in row for row in _rows(omitted))
    opted_in = _run(monkeypatch, receipt=False)
    assert opted_in.configurations == omitted.configurations
    assert [action for _, action, _, _ in opted_in.checked] == [
        action for _, action, _, _ in omitted.checked]


def test_default_trace_builder_remains_legacy_without_implicit_context(monkeypatch):
    baseline = _run(monkeypatch, labels=OMITTED, builder=None, receipt=False)
    explicit = _run(monkeypatch, labels=None, builder=None, receipt=False)
    assert explicit.result == baseline.result and explicit.raw == baseline.raw
    assert _rows(baseline)
    assert all(not {'action_index', 'opponent_archetype', 'player_name'} & set(row)
               for row in _rows(baseline))


@pytest.mark.parametrize('invalid', [
    {}, {1: 'Control'}, {1: 'Control', 2: 'Aggro', 3: 'Burn'},
    {True: 'Control', 2: 'Aggro'}, {'1': 'Control', '2': 'Aggro'},
    {1: True, 2: 'Aggro'}, {1: ['Control'], 2: 'Aggro'},
    {1: 'unknown', 2: 'Aggro'}, {1: '', 2: 'Aggro'},
], ids=['empty', 'missing-seat', 'extra-seat', 'bool-seat', 'string-seat',
        'bool-label', 'list-label', 'unknown-label', 'empty-label'])
def test_invalid_context_rejects_before_factory_or_any_native_action(monkeypatch, invalid):
    def forbidden(*args, **kwargs):
        pytest.fail('Malformed context reached native construction')
    with monkeypatch.context() as patch:
        patch.setattr(replay, 'MatchFactory', SimpleNamespace(from_decks=forbidden))
        patch.setattr(replay, 'AIAgent', forbidden)
        with pytest.raises(ValueError):
            _contextual_trace(forbidden, invalid)


@pytest.mark.parametrize('field', ['opponent_archetype', 'action_index', 'player_name'],
                         ids=['context', 'index', 'actor'])
def test_conflicting_callback_metadata_rejects_without_first_or_last_wins(monkeypatch, field):
    def conflict(*args):
        payload = _trace(*args)
        payload[field] = {'opponent_archetype': 'not-a-roster-label',
                          'action_index': True, 'player_name': 'Different actor'}[field]
        return payload
    observed = _run(monkeypatch, builder=conflict)
    assert observed.result['stop_reason'] == 'action_error'
    assert observed.result['ticks'] == 0 and observed.checked == []
    assert _rows(observed) == []


def test_conflicting_callback_announced_source_is_not_silently_overwritten(monkeypatch):
    def conflict(*args):
        payload = _trace(*args)
        if payload['action']['type'] == 'cast_spell':
            payload['action']['card_name'] = 'Forest'
        return payload
    observed = _run(monkeypatch, builder=conflict)
    assert observed.result['stop_reason'] == 'action_error'
    assert observed.result['ticks'] > 0
    assert not any(action['type'] == 'cast_spell' for _, action, _, _ in observed.checked)
    assert all(row['action']['type'] != 'cast_spell' for row in _rows(observed))


def test_explicit_context_normalization_does_not_reconfigure_the_agent(monkeypatch):
    labels = {1: ' CONTROL ', 2: ' aggro '}
    before = deepcopy(labels)
    observed = _run(monkeypatch, labels=labels)
    assert labels == before
    assert all(row['opponent_archetype'] == CONTEXTS[row['pid']].lower()
               for row in _rows(observed))
    baseline = _run(monkeypatch, labels=OMITTED, receipt=False)
    assert observed.configurations == baseline.configurations


@pytest.mark.parametrize('seat', [1, 2], ids=['seat1', 'seat2'])
def test_public_custom_actor_and_source_name_bind_existing_consumer(monkeypatch, seat):
    observed = _run(monkeypatch, seat=seat, names=('Public actor one', 'Public actor two'))
    rows = _rows(observed)
    assert rows and all(row['player_name'] == {
        1: 'Public actor one', 2: 'Public actor two'}[row['pid']] for row in rows)
    assert any(row['action']['type'] == 'cast_spell'
               and row['action']['card_name'] == 'Llanowar Elves' for row in rows)


@pytest.mark.parametrize('failure', ['checked_action', 'budget_acceptance'])
def test_refused_candidate_keeps_only_committed_prefix_identity(monkeypatch, failure):
    budget = ObservedBudget(refuse_at=3 if failure == 'budget_acceptance' else None)
    observed = _run(monkeypatch, budget=budget,
                    reject_after=3 if failure == 'checked_action' else None)
    assert observed.result['stop_reason'] == (
        'action_error' if failure == 'checked_action' else 'resource_limit')
    assert observed.result['ticks'] == budget.commits == 3
    assert [row['action_index'] for row in _rows(observed)] == [0, 1, 2]
    assert len(observed.checked) == (3 if failure == 'checked_action' else 4)
    assert budget.limits == dict(RESOURCE_LIMITS)


def test_new_metadata_reaches_same_native_budget_before_acceptance(monkeypatch):
    budget = ObservedBudget()
    deadline, limits = budget.deadline, dict(budget.limits)
    observed = _run(monkeypatch, budget=budget)
    assert budget.commits == observed.result['ticks'] == len(budget.payloads)
    assert [row['action_index'] for row in budget.payloads] == list(range(budget.commits))
    assert all(row['opponent_archetype'] == CONTEXTS[row['pid']].lower()
               for row in budget.payloads)
    assert budget.deadline == deadline and budget.limits == limits == dict(RESOURCE_LIMITS)


@pytest.mark.parametrize('seat', [1, 2], ids=['seat1', 'seat2'])
def test_real_extraction_and_reconciliation_deduplicate_actual_public_cast(monkeypatch, tmp_path, seat):
    observed = _run(monkeypatch, seat=seat)
    root = tmp_path / 'public-unit-export'
    root.mkdir()
    game = {'game': f'public-unit-seat-{seat}', 'winner': observed.result['winner'],
            'log': observed.raw}
    path = root / 'games.jsonl'
    path.write_text(json.dumps(game) + '\n', encoding='utf-8')
    examples = extract_examples_from_games_jsonl(path)
    casts = [row for row in examples if row['action_type'] == 'cast_spell']
    assert len(casts) == 1 and casts[0]['pid'] == seat
    assert casts[0]['action_card_name'] == 'Llanowar Elves'
    assert casts[0]['opponent_archetype'] == CONTEXTS[seat].lower()
    assert type(casts[0]['action_index']) is int
    # Repeated COPIES of this one real unit cast must not manufacture samples.
    copies = examples + casts + casts
    (root / 'training_examples.jsonl').write_text(
        ''.join(json.dumps(row) + '\n' for row in copies), encoding='utf-8')
    before = {item.name: item.read_bytes() for item in root.iterdir()}
    payload, unavailable = _qualified_export_contexts(root)
    assert unavailable == {}
    assert payload['samples'] == {'games': 1, 'logs': 1}
    assert payload['cards'] == {}  # One event is below even the aggregate threshold.
    assert {item.name: item.read_bytes() for item in root.iterdir()} == before
