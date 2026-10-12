"""Anonymous consumer counters in existing private diagnostic trace producers."""
from copy import deepcopy
import inspect

import pytest

from analytics.decision_quality import build_trace_payload
from game_state.state import MatchFactory, Step
from rules_engine.engine import RulesEngine
from scripts.debug_head_to_head import build_debug_trace_payload
from scripts.overnight_verbose_round_robin import _build_overnight_trace_payload
from tests.pure_snapshot_support import pure_snapshot_storage


BUILDERS = [build_trace_payload, build_debug_trace_payload, _build_overnight_trace_payload]
VALID = {'persisted': 3, 'fallback': 2, 'opaque': 7,
         'fallback_reasons': {'missing': 1, 'surface': 1}}


def trace(builder, usage):
    assert 'knowledge_usage' in inspect.signature(builder).parameters, 'Diagnostic producer discards consumer counters'
    deck = [{'card_name': 'Island', 'quantity': 60}]
    state = MatchFactory.from_decks(deck, deck, seed=173)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.UPKEEP
    args = (state, 1, RulesEngine().legal_moves(state, 1), {'type': 'pass_priority'}, 'Protocol trace')
    if builder is _build_overnight_trace_payload:
        args += ('test_protocol',)
    return builder(*args, knowledge_usage=usage)


@pytest.mark.parametrize('builder', BUILDERS)
def test_actual_trace_builder_exports_detached_anonymous_counts(builder):
    usage = deepcopy(VALID)
    payload = trace(builder, usage)
    assert payload['knowledge_usage'] == VALID
    usage['fallback_reasons']['missing'] = 99
    assert payload['knowledge_usage'] == VALID
    assert not any(key in payload['knowledge_usage'] for key in ('card_name', 'tags', 'source_sha256', 'oracle_id'))


@pytest.mark.parametrize('builder', BUILDERS)
def test_legacy_missing_counters_are_omitted_not_claimed_as_zero(builder):
    assert 'knowledge_usage' not in trace(builder, None)
    assert 'knowledge_usage' not in trace(builder, {})


@pytest.mark.parametrize('invalid', [
    {**VALID, 'card_name': 'Private card identity'},
    {**VALID, 'source_sha256': 'private-hash'},
    {**VALID, 'persisted': True},
    {**VALID, 'persisted': -1},
    {**VALID, 'persisted': float('inf')},
    {**VALID, 'persisted': 2 ** 31},
    {**VALID, 'fallback_reasons': {'Private card identity': 2}},
    {**VALID, 'fallback_reasons': {'missing': 1}},
    {**VALID, 'fallback_reasons': {'missing': True, 'surface': 1}},
])
def test_invalid_or_identity_rich_usage_never_reaches_private_trace(invalid):
    assert 'knowledge_usage' not in trace(build_trace_payload, invalid)


@pytest.mark.parametrize('builder', BUILDERS)
def test_valid_zero_consultations_are_distinct_from_absent_legacy_metadata(builder):
    usage = {'persisted': 0, 'fallback': 0, 'opaque': 0, 'fallback_reasons': {}}
    assert trace(builder, usage)['knowledge_usage'] == usage


def test_real_analytics_decisions_forward_usage_to_trace_with_pure_snapshot_storage(monkeypatch, pure_snapshot_storage):
    """Real AI/rules caller; storage protocol fixture is not a SQL certificate."""
    import json
    from pathlib import Path
    from ai.agent import AIAgent
    from analytics import service
    from tests.pure_snapshot_support import PureSnapshotRepository

    raw = next(card for card in map(json.loads, (Path(__file__).parent /
               'fixtures/knowledge_profiles/seed155-scryfall.jsonl').read_bytes().splitlines())
               if card['name'] == 'Island')
    deck = [{'card_name': raw['name'], 'quantity': 60,
             **{key: raw.get(key) for key in ('oracle_text', 'type_line', 'mana_cost', 'layout')}}]
    actual_decisions, actual_traces = [], []
    choose, build = AIAgent.choose_action, service.build_trace_payload

    def choose_record(self, *args, **kwargs):
        decision = choose(self, *args, **kwargs)
        actual_decisions.append(deepcopy(decision.knowledge_usage))
        return decision

    def build_record(*args, **kwargs):
        result = build(*args, **kwargs)
        actual_traces.append(deepcopy(result.get('knowledge_usage')))
        return result

    monkeypatch.setattr(AIAgent, 'choose_action', choose_record)
    monkeypatch.setattr(service, 'build_trace_payload', build_record)
    result = service.AnalyticsService(PureSnapshotRepository()).run_batch(
        deck, deck, matches=1, difficulty='strong', max_ticks=4)
    assert result['matches'] == 1
    assert len(actual_decisions) == len(actual_traces) > 0
    assert actual_traces == actual_decisions
