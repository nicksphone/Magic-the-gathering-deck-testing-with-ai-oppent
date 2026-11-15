"""Controlled canonical Burn sequences, not native episodes or expert labels.

Opponents explicitly pass; an unresolved opposing choice stops the continuation.
The eight positive positions and 12-own/64-total bounds match the retained E6
baseline harness. No fitted model or exact first-action requirement is used.
"""
from collections import Counter
from copy import deepcopy

import pytest

from ai.action_contract import complete_action
from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_ai_strategy_fundamentals import position
from tests.test_learned_tactical_guard import _announce_salve


RULES = RulesEngine()
CASES = (
    dict(family='two-bolts', hand=['Lightning Bolt'] * 2, mountains=2, life=6, enemy=[]),
    dict(family='three-spikes', hand=['Lava Spike'] * 3, mountains=3, life=9, enemy=[]),
    dict(family='face-lethal-with-distractor', hand=['Lightning Bolt', 'Lava Spike'],
         mountains=2, life=6, enemy=['Grizzly Bears']),
    dict(family='two-bolts-vs-development', hand=['Lightning Bolt'] * 2 + ['Monastery Swiftspear'],
         mountains=2, life=6, enemy=[]),
)


def _position(seat, spec):
    state, _, _, _ = position(
        seat, spec['hand'], ['Mountain'] * spec['mountains'], spec['enemy'])
    state.players[3-seat].life = spec['life']
    state.mechanic_choice_players = {1, 2}
    state.replacement_choice_players = {1, 2}
    state.replacement_choice_required = True
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    hand = state.players[seat].hand
    assert Counter(state.cards[cid].name for cid in hand) == Counter(spec['hand'])
    assert len(set(hand)) == len(spec['hand'])
    assert not state.players[seat].mana_pool
    assert sum(state.cards[cid].name == 'Mountain' and not state.cards[cid].tapped
               for cid in state.players[seat].battlefield) == spec['mountains']
    return state


def _play_current_turn(state, seat):
    agent = AIAgent(difficulty='master', archetype='Burn',
                    opponent_archetype='Tribal', learned_binding=None)
    initial_turn, own_count = state.turn, 0
    trace, stop = [], 'total_action_limit'
    for ordinal in range(64):
        if state.winner is not None:
            stop = 'terminal'
            break
        if state.turn != initial_turn or state.active_player != seat:
            stop = 'next_turn'
            break
        choice = (state.pending_mechanic_choice or state.pending_replacement_choice
                  or state.pending_trigger_order)
        actor = (choice.get('player_id', choice.get('current_controller'))
                 if choice else state.priority_player)
        if choice and actor != seat:
            stop = 'unknown_opponent_choice'
            break
        if actor == seat and own_count >= 12:
            stop = 'own_decision_limit'
            break
        before = serialize_match_snapshot(state)
        if actor == seat:
            moves = RULES.legal_moves(deepcopy(state), seat)
            old_moves = deepcopy(moves)
            decision = agent.choose_action(state, moves, seat)
            action = complete_action(decision.action)
            reason = decision.reasoning
            own_count += 1
            assert moves == old_moves
        else:
            assert actor == 3-seat
            action = {'type': 'pass_priority'}
            reason = 'Explicit conditional opponent pass, not an opponent policy'
        trace.append(dict(ordinal=ordinal, actor=actor, step=state.step.value,
                          own_hand=[state.cards[cid].name for cid in state.players[seat].hand],
                          opponent_life=state.players[3-seat].life,
                          action=deepcopy(action), reasoning=reason))
        candidate = checked_action(state, RULES, actor, action)
        assert serialize_match_snapshot(state) == before
        state = candidate
    if state.winner is not None:
        stop = 'terminal'
    return state, dict(initial_turn=initial_turn, stop=stop,
                       own_decisions=own_count, trace=trace)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('spec', CASES, ids=[case['family'] for case in CASES])
def test_master_burn_completes_available_current_turn_face_sequence(seat, spec):
    state, receipt = _play_current_turn(_position(seat, spec), seat)
    assert state.winner == seat and state.turn == receipt['initial_turn'], receipt


@pytest.mark.parametrize('seat', [1, 2])
def test_one_bolt_is_not_a_six_life_current_turn_win(seat):
    spec = dict(hand=['Lightning Bolt'], mountains=1, life=6, enemy=[])
    state, receipt = _play_current_turn(_position(seat, spec), seat)
    assert receipt['stop'] != 'unknown_opponent_choice', receipt
    assert state.winner is None and state.players[3-seat].life >= 3, receipt


@pytest.mark.parametrize('seat', [1, 2])
def test_real_paid_prevention_stops_two_bolts_being_a_six_life_win(seat):
    state = _position(seat, CASES[0])
    # Existing full-RAW Factory fixture: real mode, real payment, real resolution.
    state, salve = _announce_salve(state, 3-seat, 'Prevent the next')
    for _ in range(4):
        if not state.stack:
            break
        state = checked_action(state, RULES, state.priority_player, {'type': 'pass_priority'})
    assert not state.stack and state.cards[salve].zone == Zone.GRAVEYARD
    assert not any(state.players[3-seat].mana_pool.values())
    assert state.players[3-seat].prevent_damage_shield == 3
    state.active_player = state.priority_player = seat
    state.passed_priority.clear()
    state, receipt = _play_current_turn(state, seat)
    assert receipt['stop'] != 'unknown_opponent_choice', receipt
    assert state.winner is None and state.players[3-seat].life >= 3, receipt


def _damage_plan(state, seat):
    from ai.damage_sequences import winning_damage_action
    from ai.information import decision_view
    from ai.pending_effects import decision_projection_scope

    before = serialize_match_snapshot(state)
    moves = RULES.legal_moves(deepcopy(state), seat)
    old_moves = deepcopy(moves)
    view, supplied = decision_view(state, seat, moves)
    old_view = serialize_match_snapshot(view)
    old_supplied = deepcopy(supplied)
    agent = AIAgent(difficulty='master', archetype='Burn',
                    opponent_archetype='Tribal', learned_binding=None)
    with decision_projection_scope(view, seat):
        action = winning_damage_action(agent, view, supplied, seat)
    assert serialize_match_snapshot(state) == before
    assert serialize_match_snapshot(view) == old_view
    assert moves == old_moves and supplied == old_supplied
    return action


@pytest.mark.parametrize('seat', [1, 2])
def test_damage_plan_refuses_two_bolts_without_two_available_red_mana(seat):
    state = _position(seat, dict(hand=['Lightning Bolt'] * 2,
                                 mountains=1, life=6, enemy=[]))
    # One cast is genuinely affordable; a second cannot reuse its tapped land.
    offered = [move for move in RULES.legal_moves(deepcopy(state), seat)
               if move['type'] == 'cast_spell']
    assert offered
    assert _damage_plan(state, seat) is None
    cast = complete_action({**offered[0], 'cost_choice': {'id': 'base'},
                            'targets': {'target_player': 3-seat}})
    paid = checked_action(state, RULES, seat, cast)
    assert all(paid.cards[cid].tapped for cid in paid.players[seat].battlefield)
    assert not any(paid.players[seat].mana_pool.values())
    assert len(paid.players[seat].hand) == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_damage_plan_refuses_lethal_after_real_paid_prevention_resolves(seat):
    state = _position(seat, CASES[0])
    state, salve = _announce_salve(state, 3-seat, 'Prevent the next')
    for _ in range(4):
        if not state.stack:
            break
        state = checked_action(state, RULES, state.priority_player, {'type': 'pass_priority'})
    assert not state.stack and state.cards[salve].zone == Zone.GRAVEYARD
    assert not any(state.players[3-seat].mana_pool.values())
    assert state.players[3-seat].prevent_damage_shield == 3
    assert state.players[3-seat].life == 6
    state.active_player = state.priority_player = seat
    state.passed_priority.clear()
    assert _damage_plan(state, seat) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_pending_own_face_spell_continues_winning_sequence_past_creature_pressure(seat):
    state = _position(seat, dict(hand=['Lightning Bolt'] * 2,
                                 mountains=2, life=6, enemy=['Grizzly Bears']))
    first = _damage_plan(state, seat)
    assert first is not None and first['type'] == 'cast_spell'
    assert first['targets']['target_player'] == 3-seat
    state = checked_action(state, RULES, seat, complete_action(first))
    assert state.priority_player == seat
    assert len(state.stack) == 1 and state.stack[-1].controller == seat
    assert state.players[3-seat].life == 6
    assert len(state.players[seat].hand) == 1
    assert _damage_plan(state, seat) == {'type': 'pass_priority'}
    state, receipt = _play_current_turn(state, seat)
    assert receipt['trace'][0]['actor'] == seat
    assert receipt['trace'][0]['action']['type'] == 'pass_priority', receipt
    assert state.winner == seat and state.turn == receipt['initial_turn'], receipt
    assert any(state.cards[cid].name == 'Grizzly Bears'
               for cid in state.players[3-seat].battlefield), receipt


def _helix_sequence_position(seat):
    from hashlib import sha256
    import json
    from pathlib import Path

    from game_state.state import MatchFactory

    path = Path(__file__).parent / 'fixtures/beneficiary_roles/lightning-helix.json'
    data = path.read_bytes()
    assert sha256(data).hexdigest() == '2c642e23711a222966bb3ef640a669c453cb8efab38aa51ef100dbfaea95ff4b'
    raw = json.loads(data)
    assert raw['object'] == 'card' and raw['name'] == 'Lightning Helix'
    state, _, _, _ = position(seat, ['Lightning Bolt'],
                              ['Mountain', 'Mountain', 'Plains'], ['Grizzly Bears'])
    # Same retained full-RAW Factory-birth pattern as the paid-Salve fixture.
    deck = [{**raw, 'quantity': 8, 'card_name': raw['name']}]
    sample = MatchFactory.from_decks(deck, deck, seed=9104)
    card = deepcopy(sample.cards[sample.players[1].hand[0]])
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(Zone.HAND)
    state.cards[card.id] = card
    state.players[seat].hand.append(card.id)
    state.players[3-seat].life = 6
    state.mechanic_choice_players = state.replacement_choice_players = {1, 2}
    state.replacement_choice_required = state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    assert Counter(state.cards[cid].name for cid in state.players[seat].hand) == Counter(
        ['Lightning Bolt', 'Lightning Helix'])
    return state


@pytest.mark.parametrize('seat', [1, 2])
def test_master_burn_completes_helix_bolt_face_win_past_creature_pressure(seat):
    state, receipt = _play_current_turn(_helix_sequence_position(seat), seat)
    assert state.winner == seat and state.turn == receipt['initial_turn'], receipt
