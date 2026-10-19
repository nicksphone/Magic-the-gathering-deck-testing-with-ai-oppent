"""NEW-only gap audit: trusted canonical poses, real checked actions, no SQL.

Initial boards/pools are explicitly declared, not naturally paid births.
Printed full Oracle is retained; no artificial StackItems certify casts.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.information import decision_view, is_unknown
from ai.pending_effects import planning_copy
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.continuous import effective_combat_stats, has_keyword
from rules_engine.engine import RulesEngine
from rules_engine.targeting import stack_object_kind
from tests.test_task23_checked_removal_baseline import add_profiled
from tests.test_ai_knowledge_profile_consumer import RAW
from tests.vraska_full import test_full_vraska as rules

FIXTURES = Path(__file__).parent / 'fixtures/task41_lethal_canonical'
PROVENANCE = json.loads((FIXTURES / 'PROVENANCE.json').read_bytes())
CANON = {}
DECISIONS = []
for record in PROVENANCE['cards']:
    raw = (FIXTURES / record['filename']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == record['raw_sha256']
    CANON[record['name']] = json.loads(raw)


def base(seat):
    state = rules.bare(seat)
    state.turn = 6
    for player in state.players.values():
        player.mana_pool = {color: 0 for color in 'WUBRGC'}
    return state


def replay(state, enabled):
    before = serialize_match_snapshot(state)
    if enabled:
        state = deserialize_match_snapshot(deepcopy(before))
    assert serialize_match_snapshot(state) == before
    return state


def choose(state, seat, *, level='strong'):
    before = serialize_match_snapshot(state)
    moves = RulesEngine().legal_moves(state, seat)
    decision = AIAgent(difficulty=level, archetype='Midrange').choose_action(state, moves, seat)
    DECISIONS.append({'seat': seat, 'step': state.step.value,
                      'cast_candidates': sum(move['type'] == 'cast_spell' for move in moves),
                      'action_type': decision.action['type'],
                      'knowledge_usage': deepcopy(decision.knowledge_usage)})
    assert serialize_match_snapshot(state) == before, 'Policy must preserve exact input'
    return decision.action


def finish_combat(state, initial_turn):
    for _ in range(80):
        assert state.turn == initial_turn, 'A later-turn retry cannot certify this line'
        if state.winner is not None or state.step == rules.Step.END_COMBAT:
            return state
        state = rules.act(state, state.priority_player, {'type': 'pass_priority'})
    pytest.fail('Declared combat did not finish within80 genuine priority actions')


def combat_pose(seat, life):
    state = base(seat)
    state.step = rules.Step.DECLARE_ATTACKERS
    ape = add_profiled(state, CANON['Silverback Ape'], seat, rules.Zone.BATTLEFIELD)
    wolves = add_profiled(state, CANON['Tundra Wolves'], seat, rules.Zone.BATTLEFIELD)
    state.players[3 - seat].life = life
    assert effective_combat_stats(state, ape.id) == (5, 5)
    assert effective_combat_stats(state, wolves.id) == (1, 1)
    assert has_keyword(state, wolves.id, 'first strike')
    assert not has_keyword(state, wolves.id, 'double strike')
    return state, ape.id, wolves.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('roundtrip', [False, True])
@pytest.mark.parametrize('life', [6, 7])
def test_canonical_first_strike_literal_nonlethal_and_six_life_intent(seat, roundtrip, life):
    state, ape, wolves = combat_pose(seat, life)
    state = replay(state, roundtrip)
    before = serialize_match_snapshot(state)
    action = choose(state, seat)
    assert action['type'] == 'attack', f'Actual policy did not attack: {action}'
    assert set(action['attackers']) == {ape, wolves}
    result = rules.act(state, seat, action)
    result = finish_combat(result, state.turn)
    assert result.players[3 - seat].life == life - 6
    assert result.winner == (seat if life == 6 else None)
    assert serialize_match_snapshot(state) == before


def geyser_pose(seat):
    state = base(seat)
    source = add_profiled(state, CANON['Volcanic Geyser'], seat, rules.Zone.HAND)
    state.players[seat].mana_pool = {'R': 6}
    state.players[3 - seat].life = 4
    assert source.mana_cost == '{X}{R}{R}' and source.oracle_text == CANON['Volcanic Geyser']['oracle_text']
    assert any(move['type'] == 'cast_spell' and move.get('card_id') == source.id
               for move in RulesEngine().legal_moves(state, seat))
    return state, source.id


def paid_geyser(state, seat, source, action):
    assert action['type'] == 'cast_spell' and action['card_id'] == source
    assert type(action['targets']['x_value']) is int and action['targets']['x_value'] == 4
    assert action['targets']['target_player'] == 3 - seat
    before = serialize_match_snapshot(state)
    result = rules.act(state, seat, action)
    assert result.stack[-1].source_card_id == source
    assert stack_object_kind(result, result.stack[-1]) == 'spell'
    assert result.stack[-1].payload['mana_spent'] == 6
    assert sum(result.players[seat].mana_pool.values()) == 0
    result = rules.settle(result)
    assert result.winner == seat and result.players[3 - seat].life == 0
    assert result.cards[source].zone == rules.Zone.GRAVEYARD
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('roundtrip', [False, True])
def test_original_engine_legal_paid_x4_positive_not_ai_certificate(seat, roundtrip):
    state, source = geyser_pose(seat)
    state = replay(state, roundtrip)
    paid_geyser(state, seat, source, {'type': 'cast_spell', 'card_id': source,
        'targets': {'target_player': 3 - seat, 'x_value': 4}})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('roundtrip', [False, True])
def test_actual_ai_chooses_and_executes_castable_x4_not_x1(seat, roundtrip):
    state, source = geyser_pose(seat)
    state = replay(state, roundtrip)
    paid_geyser(state, seat, source, choose(state, seat))


def removal_pose(seat):
    state, ape, wolves = combat_pose(seat, 6)
    state.step = rules.Step.PRECOMBAT_MAIN
    guard = add_profiled(state, rules.BEAR, 3 - seat, rules.Zone.BATTLEFIELD)
    guard.counters['+1/+1'] = 1  # Declared old legal counter, not a paid placement certificate.
    assert effective_combat_stats(state, guard.id) == (3, 3)
    source = add_profiled(state, RAW['Go for the Throat'], seat, rules.Zone.HAND)
    state.players[seat].mana_pool = {'B': 1, 'C': 1}
    return state, source.id, guard.id, ape, wolves


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('roundtrip', [False, True])
def test_actual_ai_removes_answerable_blocker_then_same_turn_lethal_attack(seat, roundtrip):
    state, source, guard, ape, wolves = removal_pose(seat)
    state = replay(state, roundtrip)
    action = choose(state, seat)
    assert action['type'] == 'cast_spell' and action['card_id'] == source, f'Actual policy omitted removal: {action}'
    assert action['targets']['target_card_id'] == guard
    result = rules.act(state, seat, action)
    assert result.stack[-1].payload['mana_spent'] == 2
    result = rules.settle(result)
    assert result.cards[guard].zone == rules.Zone.GRAVEYARD
    assert result.cards[source].zone == rules.Zone.GRAVEYARD and not result.stack
    assert result.winner is None and result.turn == state.turn
    for _ in range(20):
        if result.step == rules.Step.DECLARE_ATTACKERS:
            break
        result = rules.act(result, result.priority_player, {'type': 'pass_priority'})
    assert result.step == rules.Step.DECLARE_ATTACKERS and result.turn == state.turn
    attack = choose(result, seat)
    assert attack['type'] == 'attack' and set(attack['attackers']) == {ape, wolves}
    result = rules.act(result, seat, attack)
    result = finish_combat(result, state.turn)
    assert result.winner == seat and result.players[3 - seat].life == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_genuine_counterspell_response_prevents_forced_removal_win(seat):
    state, source, guard, ape, wolves = removal_pose(seat)
    response = add_profiled(state, RAW['Counterspell'], 3 - seat, rules.Zone.HAND)
    state.players[3 - seat].mana_pool = {'U': 2}
    result = rules.act(state, seat, {'type': 'cast_spell', 'card_id': source,
                                    'targets': {'target_card_id': guard}})
    removal_stack_id = result.stack[-1].id
    result = rules.act(result, seat, {'type': 'pass_priority'})
    answer = choose(result, 3 - seat)
    assert answer['type'] == 'cast_spell' and answer['card_id'] == response.id
    assert answer['targets']['target_stack_id'] == removal_stack_id
    result = rules.act(result, 3 - seat, answer)
    assert result.stack[-1].payload['mana_spent'] == 2
    result = rules.settle(result)
    assert result.cards[guard].zone == rules.Zone.BATTLEFIELD and result.winner is None
    assert result.cards[source].zone == rules.Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_private_hand_window_does_not_become_proved_combat_leaf(seat):
    state, ape, wolves = combat_pose(seat, 6)
    hidden = add_profiled(state, RAW['Counterspell'], 3 - seat, rules.Zone.HAND)
    before = serialize_match_snapshot(state)
    public, _ = decision_view(state, seat, RulesEngine().legal_moves(state, seat))
    assert is_unknown(public.cards[hidden.id])
    actor = AIAgent(difficulty='strong', archetype='Midrange')
    candidate = rules.act(state, seat, {'type': 'attack', 'attackers': [ape, wolves]})
    assert actor._complete_strategic_combat_leaf(planning_copy(candidate), seat) is None
    assert serialize_match_snapshot(state) == before
