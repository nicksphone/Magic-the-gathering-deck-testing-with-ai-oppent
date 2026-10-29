"""Canonical public response poses; no replay, model, or private fixture input."""
import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.pending_permanent_fullraw import raw_card
from tests.browser_positive83_canonical import raw_card as basic_raw
from tests.test_ai_own_only_sweeper import RAW
from tests.test_ai_recurring_engines import add, fixture
from tests.test_any_player_cast_damage import settle


RECEIPTS = []


def response_pose(seat, life=11):
    state = fixture()
    state.turn = 16
    state.active_player = state.priority_player = 3-seat
    state.players[seat].life, state.players[3-seat].life = life, 6
    for player in state.players.values():
        player.mana_pool = {color: 0 for color in 'WUBRGC'}
        player.snow_mana_pool.clear()
    for i, name in enumerate(['Island'] * 5 + ['Plains'] * 3):
        add(state, name, seat, cards=RAW).tapped = i == 0
    for name in ['Mountain'] * 4 + ['Plains'] * 3 + ['Plateau']:
        add(state, name, 3-seat, cards=RAW)
    bodies = []
    for name in ['Cosmos Charger', 'Augury Raven']:
        body = add(state, name, seat, cards=RAW)
        body.tapped, body.summoning_sick = True, False
        bodies.append(body.id)
    sword = add(state, 'Swords to Plowshares', seat, Zone.HAND, cards=RAW)
    add(state, 'Island', seat, Zone.HAND, cards=RAW)
    burn = add(state, 'Lava Spike', 3-seat, Zone.HAND, cards=RAW)
    rules = RulesEngine()
    state = checked_action(state, rules, 3-seat, {
        'type': 'cast_spell', 'card_id': burn.id, 'targets': {'target_player': seat}})
    state = checked_action(state, rules, 3-seat, {'type': 'pass_priority'})
    assert state.priority_player == seat and not state.players[3-seat].hand
    assert len(state.stack) == 1
    return state, sword.id, bodies


def next_combat(state, seat, bodies):
    """Only advance the canonical empty opposing board to one native combat."""
    rules = RulesEngine()
    for _ in range(64):
        if state.active_player == seat and state.step == Step.DECLARE_ATTACKERS:
            break
        assert state.winner is None and not state.stack
        state = checked_action(state, rules, state.priority_player, {'type': 'pass_priority'})
    else:
        raise AssertionError('Did not reach next canonical attack')
    attackers = [cid for cid in bodies if state.cards[cid].zone == Zone.BATTLEFIELD]
    state = checked_action(state, rules, seat, {
        'type': 'attack', 'attackers': attackers,
        'attack_targets': {cid: f'player:{3-seat}' for cid in attackers}})
    for _ in range(16):
        if state.winner is not None or state.step == Step.COMBAT_DAMAGE:
            return state
        state = checked_action(state, rules, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Canonical attack did not reach damage')


def decide(state, seat):
    agent = AIAgent('master', 'Control', opponent_archetype='Burn')
    before = serialize_match_snapshot(state)
    moves = agent.engine.legal_moves(state, seat)
    decision = agent.choose_action(state, moves, seat)
    checked_action(state, agent.engine, seat, decision.action)
    assert serialize_match_snapshot(state) == before
    RECEIPTS.append({'seat': seat, 'initial': before, 'offers': moves,
                     'action': decision.action, 'reasoning': decision.reasoning})
    return decision


@pytest.mark.parametrize('seat', [1, 2])
def test_nonlethal_burn_response_keeps_next_combat_lethal(seat):
    state, sword, bodies = response_pose(seat)
    before = serialize_match_snapshot(state)
    baseline = settle(state)
    assert baseline.players[seat].life == 8 and baseline.winner is None
    response = settle(checked_action(state, RulesEngine(), seat, {
        'type': 'cast_spell', 'card_id': sword,
        'targets': {'target_card_id': bodies[0]}}))
    assert response.players[seat].life == 11
    assert response.cards[bodies[0]].zone == Zone.EXILE
    assert next_combat(baseline, seat, bodies).winner == seat
    after_response_combat = next_combat(response, seat, bodies)
    assert after_response_combat.winner is None
    assert after_response_combat.players[3-seat].life == 3
    decision = decide(state, seat)
    assert serialize_match_snapshot(state) == before
    assert decision.action == {'type': 'pass_priority'}, decision.reasoning


@pytest.mark.parametrize('seat', [1, 2])
def test_self_exile_still_prevents_lethal_burn(seat):
    state, sword, bodies = response_pose(seat, life=2)
    assert settle(state).winner == 3-seat
    decision = decide(state, seat)
    assert decision.action.get('card_id') == sword
    assert decision.action['targets']['target_card_id'] in bodies
    saved = settle(checked_action(state, RulesEngine(), seat, decision.action))
    assert saved.winner is None and saved.players[seat].life == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_winning_death_response_is_preserved(seat):
    state, _, _ = response_pose(seat)
    state.players[3-seat].life = 1
    cards = {name: raw_card(name) for name in ['Bastion of Remembrance', 'Murder']}
    add(state, 'Bastion of Remembrance', seat, cards=cards)
    murder = add(state, 'Murder', seat, Zone.HAND, cards=cards)
    for _ in range(3):
        add(state, 'Swamp', seat, cards={'Swamp': basic_raw('Swamp')})
    decision = decide(state, seat)
    assert decision.action.get('card_id') == murder.id
    won = settle(checked_action(state, RulesEngine(), seat, decision.action))
    assert won.winner == seat and won.players[3-seat].life == 0
