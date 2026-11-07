"""A bounded heuristic is a choice policy, never an exhaustive win proof."""
from copy import deepcopy
import pickle

import pytest

from ai import block_search
from ai.agent import AIAgent
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_ai_block_query_scope import board


@pytest.mark.parametrize('seat', [1, 2])
def test_large_shortlist_is_legal_stable_pure_and_keeps_no_block(seat):
    state, attackers, blockers = board(seat, count=4, guards=5)
    intents = block_search.block_intents(state, attackers, blockers)
    before = pickle.dumps((state, intents), protocol=5)
    assert len(intents) == 3125
    shortlist = block_search.block_projection_intents(state, intents)
    assert 1 < len(shortlist) <= 16
    assert {} in shortlist
    assert shortlist == block_search.block_projection_intents(state, list(reversed(intents)))
    assert len({repr(sorted((aid, sorted(bids)) for aid, bids in row.items()))
                for row in shortlist}) == len(shortlist)
    for row in shortlist:
        assert row in intents
        checked_action(state, RulesEngine(), 3-seat, {'type': 'block', 'blocks': row})
    assert pickle.dumps((state, intents), protocol=5) == before


def test_small_search_keeps_every_original_intent_in_order():
    state, attackers, blockers = board(count=3, guards=3)
    intents = block_search.block_intents(state, attackers, blockers)
    assert len(intents) == 64
    assert block_search.block_projection_intents(state, intents) is intents


@pytest.mark.parametrize('unknown', [(None, 2), (2, None)])
def test_unknown_public_characteristic_keeps_large_forecast_unknown(unknown, monkeypatch):
    # Protocol boundary: the public query explicitly permits either unknown stat.
    import rules_engine.continuous as continuous
    state, attackers, blockers = board(count=4, guards=5)
    intents = block_search.block_intents(state, attackers, blockers)
    before = pickle.dumps(state, protocol=5)
    stats = continuous.effective_combat_stats
    monkeypatch.setattr(continuous, 'effective_combat_stats',
                        lambda root, cid: unknown if cid == attackers[0] else stats(root, cid))
    assert block_search.block_projection_intents(state, intents) is None
    assert AIAgent('master')._search_block_assignments(state,
        [{'id': cid} for cid in attackers], [{'id': cid} for cid in blockers]) is None
    assert pickle.dumps(state, protocol=5) == before


def test_attack_forecast_requests_complete_defensive_coverage(monkeypatch):
    from game_state.state import Step
    state, attackers, _ = board(count=1, guards=1)
    state.step = Step.DECLARE_ATTACKERS
    state.priority_player = state.active_player
    state.attackers = []
    state.attackers_declared = False
    state.cards[attackers[0]].tapped = False
    agent = AIAgent('master')
    observed = []

    def unresolved(*args, **kwargs):
        observed.append(kwargs.get('require_complete'))
        return None

    monkeypatch.setattr(agent, '_search_block_assignments', unresolved)
    assert agent._project_attack_line(state, state.active_player, attackers) is None
    assert observed == [True]


@pytest.mark.parametrize('seat', [1, 2])
def test_native_projection_count_is_bounded_and_still_prevents_lethal(seat, monkeypatch):
    state, attackers, blockers = board(seat, count=4, guards=5)
    state.players[3-seat].life = 2
    before = pickle.dumps(state, protocol=5)
    agent = AIAgent('master')
    finish = agent._finish_combat_projection
    calls = []

    def observed(sim, original):
        calls.append(deepcopy(sim.blocks))
        if len(calls) > 16:
            pytest.fail('Native simulations must not scale with all3125 assignments')
        return finish(sim, original)

    monkeypatch.setattr(agent, '_finish_combat_projection', observed)
    choice = agent._search_block_assignments(state, [{'id': cid} for cid in attackers],
        [{'id': cid} for cid in blockers], consider_next_combat=False)
    assert choice is not None and 0 < len(calls) <= 16
    assert pickle.dumps(state, protocol=5) == before
    normalized = {aid: [bids] if isinstance(bids, str) else bids for aid, bids in choice.items()}
    sim = checked_action(state, RulesEngine(), 3-seat, {'type': 'block', 'blocks': normalized})
    assert finish(sim, state) and sim.winner != seat
    assert sim.players[3-seat].life > 0


def test_exact_response_over_budget_remains_unknown_without_projection(monkeypatch):
    state, attackers, blockers = board(count=4, guards=5)
    agent = AIAgent('master')
    monkeypatch.setattr(agent, '_finish_combat_projection',
                        lambda *_: pytest.fail('An incomplete response cannot be a win certificate'))
    assert agent._search_block_assignments(state, [{'id': cid} for cid in attackers],
        [{'id': cid} for cid in blockers], require_complete=True) is None


def test_one_unknown_defense_prevents_complete_response_claim(monkeypatch):
    state, attackers, blockers = board(count=1, guards=1)
    agent = AIAgent('master')
    finish = agent._finish_combat_projection

    def uncertain_block(sim, original):
        return False if sim.blocks else finish(sim, original)

    monkeypatch.setattr(agent, '_finish_combat_projection', uncertain_block)
    assert agent._search_block_assignments(state, [{'id': cid} for cid in attackers],
        [{'id': cid} for cid in blockers], require_complete=True) is None
