"""Real production payload + native-prefix controls, not completed AI matches.

Reuse the original canonical Factory/checked-action prefix without editing it.
The caller's unknown/unresolved branch is exercised separately in the matrix
protocol module; OMITTED here is that unchanged legacy builder selection.
The receipt sink is still in-memory unit-only, not native-export admission.
"""
import pytest

from analytics.decision_quality import build_trace_payload
from tests.test_task33_native_producer_context import (
    CONTEXTS, OMITTED, ObservedBudget, _rows, _run,
)


def _production_trace(state, pid, legal, action, decision):
    return build_trace_payload(state, pid, legal, action, getattr(decision, 'reasoning', ''),
                               knowledge_usage=getattr(decision, 'knowledge_usage', None))


@pytest.mark.parametrize('seat', [1, 2], ids=['seat1', 'seat2'])
@pytest.mark.parametrize('mode', ['known', 'legacy-unavailable'])
def test_real_builder_native_prefix_never_loses_accepted_actions(monkeypatch, seat, mode):
    budget = ObservedBudget()
    labels = CONTEXTS if mode == 'known' else OMITTED
    observed = _run(monkeypatch, seat=seat, labels=labels, builder=_production_trace, budget=budget)
    rows = _rows(observed)
    assert observed.result.get('stop_reason') is None
    assert observed.result['ticks'] == len(observed.checked) == len(rows) == budget.commits == 16
    assert observed.result['winner'] is None  # Bounded prefix, never a finished match.
    casts = [row for row in rows if row['action']['type'] == 'cast_spell']
    assert casts and any(row['pid'] == seat for row in casts)
    assert len(observed.callback_payloads) == len(rows)
    for index, (row, (raw, before), (pid, action, _, _)) in enumerate(zip(
            rows, observed.callback_payloads, observed.checked)):
        assert raw == before and row['pid'] == pid
        # The REAL compact_action follows complete_action. Defaults may be
        # absent, but every retained operand must be the actual checked action.
        assert {key: value for key, value in raw['action'].items()} == {
            key: action[key] for key in raw['action']}
        assert 'card_name' not in raw['action']
        assert row['hand'] == raw['hand'] and row['opp_hand'] == raw['opp_hand']
        expected = {**raw, 'action': dict(raw['action'])}
        if mode == 'known':
            expected.update(opponent_archetype=CONTEXTS[pid].lower(),
                            action_index=index, player_name={1: 'Player A', 2: 'Player B'}[pid])
            if action['type'] == 'cast_spell':
                expected['action']['card_name'] = 'Llanowar Elves'
        assert row == expected
