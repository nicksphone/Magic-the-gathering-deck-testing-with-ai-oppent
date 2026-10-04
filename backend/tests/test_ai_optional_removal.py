"""Shared removal policy: conserve resources without banning death-trigger wins."""
import pytest

from ai.agent import AIAgent
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_ai_search_prefix import bare_state
from tests.test_pending_removal import add_card
from tests.test_ai_recurring_engines import add


def position(seat, spell, payoff=False):
    state = bare_state(seat)
    state.turn = 12
    state.players[seat].mana_pool = {'B': 2, 'C': 2}
    source = add_card(state, spell, Zone.HAND, seat)
    victim = add(state, 'Grizzly Bears', seat)
    if payoff:
        add(state, 'Blood Artist', seat)
        state.players[3-seat].life = 1
    return state, source, victim


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('spell', ['Fatal Push', 'Go for the Throat'])
@pytest.mark.parametrize('style', ['Control', 'Ramp', 'Aggro', 'Tempo', 'Tokens', 'Drain'])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
def test_no_forced_cast_wastes_pure_removal_on_own_unthreatened_creature(seat, spell, style, difficulty):
    state, source, victim = position(seat, spell)
    before = serialize_match_snapshot(state)
    moves = RulesEngine().legal_moves(state, seat)
    decision = AIAgent(archetype=style, difficulty=difficulty).choose_action(state, moves, seat)
    assert decision.action['type'] == 'pass_priority'
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, RulesEngine(), seat, decision.action)
    assert source.id in state.players[seat].hand and victim.id in state.players[seat].battlefield


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('spell', ['Fatal Push', 'Go for the Throat'])
@pytest.mark.parametrize('style', ['Control', 'Ramp', 'Aggro', 'Tempo', 'Tokens', 'Drain'])
def test_friendly_removal_with_real_targeted_death_trigger_can_win(seat, spell, style):
    state, source, _ = position(seat, spell, payoff=True)
    state.mechanic_choice_players = state.trigger_order_choice_players = {1, 2}
    state.trigger_order_choice_required = True
    ai = AIAgent(archetype=style, difficulty='master')
    before = serialize_match_snapshot(state)
    decision = ai.choose_action(state, RulesEngine().legal_moves(state, seat), seat)
    assert decision.action['type'] == 'cast_spell'
    assert decision.action['card_id'] == source.id
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, RulesEngine(), seat, decision.action)
    for _ in range(32):
        if state.winner is not None:
            break
        pending = state.pending_trigger_order or state.pending_mechanic_choice or state.pending_replacement_choice
        actor = pending.get('current_controller', pending.get('player_id')) if pending else state.priority_player
        moves = RulesEngine().legal_moves(state, actor)
        action = ai.choose_action(state, moves, actor).action if pending else {'type': 'pass_priority'}
        state = checked_action(state, RulesEngine(), actor, action)
    assert state.winner == seat


@pytest.mark.parametrize('seat', [1, 2])
def test_optional_policy_does_not_hide_legal_enemy_removal(seat):
    state, source, victim = position(seat, 'Fatal Push')
    state.players[seat].battlefield.remove(victim.id)
    victim.controller = victim.owner = 3-seat
    state.players[3-seat].battlefield.append(victim.id)
    ai = AIAgent(archetype='Control', difficulty='master')
    decision = ai.choose_action(state, RulesEngine().legal_moves(state, seat), seat)
    assert decision.action['type'] == 'cast_spell'
    assert decision.action['targets']['target_card_id'] == victim.id
