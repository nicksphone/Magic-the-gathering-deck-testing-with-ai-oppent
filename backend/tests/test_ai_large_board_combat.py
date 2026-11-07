"""Public canonical board poses, not private replays or exhaustive win proofs."""
from copy import deepcopy

import pytest

from ai.agent import AIAgent
from ai.information import decision_view
from ai.pending_effects import unanswered_action_wins
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_ai_strategy_fundamentals import position
from tests.combat_canonical_022 import raw_card
from tests.test_linked_damage_targets import raw_card as birth


RULES = RulesEngine()


def board(seat, count=7, blockers=3, *, attacker='Grizzly Bears', guard='Grizzly Bears'):
    state, _, _, move = position(seat, [], ['Mountain'] * 4,
        enemy=[guard] * blockers, reserve=[attacker] * count)
    attackers = [move(attacker, seat, Zone.BATTLEFIELD) for _ in range(count)]
    state.turn = 12
    state.step = Step.DECLARE_ATTACKERS
    state.players[3-seat].life = 3
    state.mechanic_choice_players = state.replacement_choice_players = {1, 2}
    state.trigger_order_choice_players = {1, 2}
    state.trigger_order_choice_required = True
    return state, attackers


def announced(state, seat, attackers):
    return checked_action(state, RULES, seat, {'type': 'attack', 'attackers': attackers})


def creature(state, name, seat):
    card = birth(state, raw_card(name), seat, Zone.BATTLEFIELD)
    card.summoning_sick = False
    assign_static_order_on_battlefield_entry(state, card.id)
    return card.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('count', [7, 12])
def test_large_board_conditional_forecast_resolves_existing_block_policy(seat, count):
    state, attackers = board(seat, count)
    agent = AIAgent('master', 'Tribal', 'Burn')
    before = serialize_match_snapshot(state)
    attack = announced(state, seat, attackers)
    attack_before = serialize_match_snapshot(attack)
    forecast = agent._forecast_strategic_combat(attack)
    assert forecast is not None, 'Cardinality alone must not hide the conditional combat horizon'
    assert forecast.winner == seat and forecast.players[3-seat].life <= 0
    assert serialize_match_snapshot(state) == before
    assert serialize_match_snapshot(attack) == attack_before


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_master_compares_completed_attack_with_waiting(seat):
    state, attackers = board(seat)
    agent = AIAgent('master', 'Tribal', 'Burn')
    moves = RULES.legal_moves(deepcopy(state), seat)
    before, moves_before = serialize_match_snapshot(state), deepcopy(moves)
    decision = agent.choose_action(state, moves, seat)
    assert decision.action['type'] == 'attack', decision
    assert set(decision.action['attackers']) == set(attackers)
    checked_action(state, RULES, seat, decision.action)
    assert serialize_match_snapshot(state) == before and moves == moves_before
    hidden = deepcopy(state)
    for player in hidden.players.values():
        player.library.reverse()
    assert agent.choose_action(hidden, moves, seat).action == decision.action


@pytest.mark.parametrize('seat', [1, 2])
def test_heuristic_horizon_is_not_an_unanswered_attack_certificate(seat):
    state, attackers = board(seat)
    move = {'type': 'attack', 'attackers': attackers}
    view, _ = decision_view(state, seat, [])
    assert unanswered_action_wins(view, seat, move, settle_declared_combat=True) is not True
    attack = announced(view, seat, attackers)
    assert AIAgent('master')._complete_strategic_combat_leaf(attack, seat) is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('count,blockers', [(17, 3), (7, 9)])
def test_large_forecast_cardinality_budget_keeps_unknown(seat, count, blockers):
    state, attackers = board(seat, count, blockers)
    attack = announced(state, seat, attackers)
    before = serialize_match_snapshot(attack)
    assert AIAgent('master')._forecast_strategic_combat(attack) is None
    assert serialize_match_snapshot(attack) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('boundary', ['unannounced', 'pending', 'unsupported'])
def test_existing_unknown_boundaries_remain_unknown(seat, boundary):
    state, attackers = board(seat)
    attack = state if boundary == 'unannounced' else announced(state, seat, attackers)
    if boundary == 'pending':
        attack.pending_mechanic_choice = {'kind': 'unknown-test-choice', 'player_id': seat}
    elif boundary == 'unsupported':
        # Explicit parser-negative mutation, never represented as canonical Oracle.
        attack.cards[attackers[0]].oracle_text = "As long as an unknown condition, this creature can't be blocked."
    before = serialize_match_snapshot(attack)
    assert AIAgent('master')._forecast_strategic_combat(attack) is None
    assert serialize_match_snapshot(attack) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_large_forecast_does_not_enumerate_block_tree(monkeypatch, seat):
    import ai.block_search

    def forbidden(*args, **kwargs):
        pytest.fail('Large conditional forecast must not expand the exhaustive tree')

    monkeypatch.setattr(ai.block_search, 'block_intents', forbidden)
    state, attackers = board(seat)
    assert AIAgent('master')._forecast_strategic_combat(announced(state, seat, attackers)) is not None


@pytest.mark.parametrize('seat', [1, 2])
def test_small_search_exhaustion_does_not_use_large_board_fallback(monkeypatch, seat):
    state, attackers = board(seat, 4)
    agent = AIAgent('master')
    monkeypatch.setattr(agent, '_search_block_assignments', lambda *args, **kwargs: None)
    monkeypatch.setattr(agent, '_choose_blocks', lambda *args: pytest.fail('Small exhaustion stays unknown'))
    assert agent._forecast_strategic_combat(announced(state, seat, attackers)) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_invalid_heuristic_declaration_remains_unknown(monkeypatch, seat):
    state, attackers = board(seat)
    attack = announced(state, seat, attackers)
    before = serialize_match_snapshot(attack)
    agent = AIAgent('master')
    monkeypatch.setattr(agent, '_choose_blocks', lambda *args: {attackers[0]: ['not-an-offered-blocker']})
    assert agent._forecast_strategic_combat(attack) is None
    assert serialize_match_snapshot(attack) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_one_unlimited_capacity_defender_is_not_three_small_blockers(seat):
    state, attackers = board(seat, blockers=0)
    creature(state, 'Palace Guard', 3-seat)
    attack = announced(state, seat, attackers)
    before = serialize_match_snapshot(attack)
    forecast = AIAgent('master')._forecast_strategic_combat(attack)
    assert forecast is not None and forecast.winner is None
    assert forecast.players[3-seat].life == 3
    assert serialize_match_snapshot(attack) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_control_can_wait_and_defender_is_never_an_attacker(seat):
    state, _ = board(seat, count=0, blockers=0)
    for _ in range(7):
        creature(state, 'Llanowar Elves', seat)
    for _ in range(3):
        creature(state, 'Serra Angel', 3-seat)
    wall = creature(state, 'Wall of Omens', seat)
    state.players[3-seat].life = 20
    before = serialize_match_snapshot(state)
    moves = RULES.legal_moves(deepcopy(state), seat)
    action = AIAgent('master', 'Control', 'Aggro').choose_action(state, moves, seat).action
    assert wall not in action.get('attackers', [])
    assert action['type'] == 'pass_priority' or (action['type'] == 'attack' and not action['attackers'])
    checked_action(state, RULES, seat, action)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('tax', ['War Tax', 'War Cadence'])
def test_actual_paid_tax_does_not_become_free_progress(seat, tax):
    from tests.test_combat_domain_temporary_costs import activate

    state, attackers = board(seat)
    state, _ = activate(state, tax, 3-seat if tax == 'War Tax' else seat, 20)
    state.active_player = state.priority_player = seat
    for player in state.players.values():
        player.mana_pool.clear()
    before = serialize_match_snapshot(state)
    agent = AIAgent('master', 'Tribal', 'Burn')
    if tax == 'War Cadence':
        # The greedy assignment cannot pay; unknown, not invented free blocks.
        assert agent._forecast_strategic_combat(announced(state, seat, attackers)) is None
    else:
        moves = RULES.legal_moves(deepcopy(state), seat)
        action = agent.choose_action(state, moves, seat).action
        assert not action.get('attackers')
        checked_action(state, RULES, seat, action)
    assert serialize_match_snapshot(state) == before
