"""Unexecuted native-prefix regressions, not completed games or training data."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace

import pytest

from ai.log_priors import _opponent_archetype
from analytics.resource_budget import ResourceBudget
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine import engine as native_engine
from rules_engine.action_validation import checked_action
from scripts import regression_matrix_replay as replay
from scripts.build_ai_log_priors import _qualified_export_contexts
from scripts.extract_training_examples import extract_examples_from_games_jsonl
from tests.test_forge_human_replacement_order import balances, cast_action, setup


@pytest.mark.parametrize('seat', [1, 2], ids=['seat1', 'seat2'])
@pytest.mark.parametrize('steps', [1, 3], ids=['pending-intent', 'later-completion'])
def test_only_announced_native_cast_can_supply_context_samples(monkeypatch, tmp_path, seat, steps):
    # Existing full-RAW Factory birth and two genuinely paid/resolved Salves.
    # C2 is the unchanged established-resource pose in the existing cast-owner test.
    budget = ResourceBudget()
    initial, forges, spell, _ = setup(seat)
    initial.players[seat].mana_pool['C'] = 2
    before = serialize_match_snapshot(initial)
    decks = deepcopy(initial.starting_decks)
    inventory = deepcopy(initial.sideboard_facts['inventory'])
    receipts = list(balances(initial))
    cast_count = initial.spells_cast_this_turn[seat]
    actor = initial.players[seat].name
    announcement = actor + ' casts/activates Wrath of God.'
    observed = SimpleNamespace(transitions=[], publications=[], raw=None, factory_calls=0)
    real_publish = native_engine.add_to_stack

    assert cast_count == 2 and len(receipts) == 2
    assert balances(initial) == {key: 3 for key in receipts}
    assert initial.cards[spell].name == 'Wrath of God'
    assert initial.cards[spell].mana_cost == '{2}{W}{W}'
    assert initial.cards[spell].zone == Zone.HAND and not initial.stack
    assert initial.mana_continuation is None and announcement not in initial.log

    def prepared_factory(left, right, **options):
        # The returned board was made by the REAL existing Factory/setup above.
        # This runner seam does not create a card, receipt, pending state or stack.
        assert left == decks[1] and right == decks[2] and options == {'seed': 618}
        observed.factory_calls += 1
        assert observed.factory_calls == 1
        return initial

    class PublicChooser:
        def __init__(self, **configuration):
            pass

        def choose_action(self, state, moves, pid):
            assert pid == seat
            ordinal = len(observed.transitions)
            if ordinal == 0:
                assert any(move.get('type') == 'cast_spell' and move.get('card_id') == spell
                           for move in moves)
                action = cast_action(state.cards[spell])
            else:
                expected = 'numeric-prevention:' + receipts[ordinal - 1]
                selected = [move for move in moves
                            if move.get('type') == 'choose_replacement'
                            and move.get('replacement_source_id') == expected]
                assert len(selected) == 1
                action = deepcopy(selected[0])
            return SimpleNamespace(action=action, reasoning='public native-prefix control')

    def observe_publication(*args, **kwargs):
        item = real_publish(*args, **kwargs)
        if item.source_card_id == spell:
            observed.publications.append(item)
        return item

    def observe_checked(state, rules, pid, action):
        unchanged = serialize_match_snapshot(state)
        candidate = checked_action(state, rules, pid, action)
        assert serialize_match_snapshot(state) == unchanged
        assert candidate.log[:len(state.log)] == state.log
        assert candidate.starting_decks == decks
        assert candidate.sideboard_facts['inventory'] == inventory
        observed.transitions.append((deepcopy(action), candidate,
                                     list(candidate.log[len(state.log):])))
        return candidate

    def trace(state, pid, moves, action, decision):
        return {'trace': True, 'pid': pid, 'turn': state.turn,
                'action': deepcopy(action)}

    def record(result, raw):
        # In-memory public unit receipt, not a durable execution certificate.
        observed.raw = list(raw)
        encoded = json.dumps(raw, ensure_ascii=True, separators=(',', ':'),
                             allow_nan=False).encode('utf-8')
        return {'complete': True, 'bytes': len(encoded),
                'raw_sha256': hashlib.sha256(encoded).hexdigest(),
                'reference': 'game-01.json'}

    with monkeypatch.context() as patch:
        patch.setattr(replay, 'MatchFactory', SimpleNamespace(from_decks=prepared_factory))
        patch.setattr(replay, 'AIAgent', PublicChooser)
        patch.setattr(replay, 'checked_action', observe_checked)
        patch.setattr(native_engine, 'add_to_stack', observe_publication)
        result = replay.run_game(decks[1], decks[2], 618, 'strong', steps,
            starting_player=seat, budget=budget, record_game=record,
            trace_builder=replay.contextual_trace(trace, {1: 'Control', 2: 'Aggro'}))

    assert result.get('stop_reason') is None
    assert result['ticks'] == len(observed.transitions) == steps
    assert result['winner'] is None and result['timeout'] is True
    assert serialize_match_snapshot(initial) == before
    for ordinal, (action, candidate, appended) in enumerate(observed.transitions):
        if ordinal < 2:
            assert candidate.pending_replacement_choice is not None
            assert candidate.mana_continuation['origin']['action_kind'] == 'cast_spell'
            assert candidate.cards[spell].zone == Zone.HAND and not candidate.stack
            assert candidate.spells_cast_this_turn[seat] == cast_count
            assert announcement not in appended
        else:
            assert action['type'] == 'choose_replacement'
            assert candidate.pending_replacement_choice is None
            assert candidate.mana_continuation is None
            assert candidate.spells_cast_this_turn[seat] == cast_count + 1
            assert appended.count(announcement) == 1
            assert len(candidate.stack) == len(observed.publications) == 1
            assert candidate.stack[0] is observed.publications[0]
            item = candidate.stack[0]
            assert item.source_card_id == spell and item.controller == seat
            assert item.label == 'Wrath of God'
            assert item.payload['__announced_stack_kind'] == 'spell'
            assert candidate.cards[spell].zone == Zone.STACK
            assert balances(candidate) == {key: 2 for key in receipts}
            assert all(candidate.cards[cid].tapped for cid in forges)
    assert len(observed.publications) == (1 if steps == 3 else 0)

    traces = [json.loads(line[len('AI TRACE '):]) for line in observed.raw
              if line.startswith('AI TRACE ')]
    assert [row['action_index'] for row in traces] == list(range(steps))
    assert [row['action']['type'] for row in traces] == [
        'cast_spell', *(['choose_replacement', 'choose_replacement'] if steps == 3 else [])]
    # A genuine later completion is NOT retroactively assigned to index zero,
    # nor relabelled as a fresh cast action at the replacement-choice index.
    assert all('card_name' not in row['action'] for row in traces[1:])

    (tmp_path / 'games.jsonl').write_text(json.dumps({
        'game': 'public-paused-cast-unit', 'winner': None, 'log': observed.raw}) + '\n',
        encoding='utf-8')
    examples = extract_examples_from_games_jsonl(tmp_path / 'games.jsonl')
    assert len(examples) == steps
    (tmp_path / 'training_examples.jsonl').write_text(
        ''.join(json.dumps(row) + '\n' for row in examples), encoding='utf-8')
    priors, unavailable = _qualified_export_contexts(tmp_path)
    assert 'conflicting_action_provenance' not in unavailable
    assert _opponent_archetype(traces[0]) is None, 'Pending intent certified cast context'
    assert 'card_name' not in traces[0]['action'], 'Pending intent certified announced name'
    assert _opponent_archetype(examples[0]) is None
    assert examples[0]['action_card_name'] is None
    assert priors['samples']['logs'] == 0, 'Unannounced intent entered contextual samples'
    assert priors['cards'] == {}
