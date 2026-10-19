"""Canonical checked defender decisions, not duplicate empty-board attacks."""
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.information import decision_view
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_empty_hand_attack_witness import ROWS, finish_combat, position
from tests.test_linked_damage_targets import raw_card


STYLES = ['Aggro', 'Burn', 'Control', 'Tempo', 'Midrange', 'Ramp', 'Drain',
          'Aristocrats', 'Tokens', 'Tribal']
FAMILIES = ['Sheoldred, the Apocalypse', 'Torrential Gearhulk']


class TraceAgent(AIAgent):
    def __init__(self, style):
        super().__init__(difficulty='master', archetype=style)
        self.forecasts = []

    def _next_board_attack_wins(self, state, player_id):
        result = super()._next_board_attack_wins(state, player_id)
        self.forecasts.append({'player_id': player_id, 'step': state.step.value,
            'life': {str(pid): player.life for pid, player in state.players.items()},
            'result': result})
        return result


def record(name, value):
    path = Path(os.environ['MTG_BLOCK_AUDIT_EVIDENCE'])
    path.mkdir(parents=True, exist_ok=True)
    with (path / (name + '.json')).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def defender_position(seat, blocker_name, *, case):
    attacker_name = ('Monastery Swiftspear' if case == 'safe' else
                     'Torrential Gearhulk' if blocker_name == 'Sheoldred, the Apocalypse'
                     else 'Sheoldred, the Apocalypse')
    life = int(ROWS[attacker_name]['power']) if case == 'lethal_trade' else 20
    state, attacker = position(3-seat, attacker_name, opponent_life=life)
    blocker = raw_card(state, ROWS[blocker_name], seat, Zone.BATTLEFIELD)
    blocker.summoning_sick = False
    if case == 'race':
        state.players[3-seat].life = int(ROWS[blocker_name]['power'])
    for _ in range(2):
        raw_card(state, ROWS['Island'], seat, Zone.BATTLEFIELD)
    raw_card(state, ROWS['Counterspell'], seat, Zone.HAND)
    engine = RulesEngine()
    state = checked_action(state, engine, 3-seat, {'type': 'attack', 'attackers': [attacker]})
    for _ in range(20):
        legal = engine.legal_moves(state, seat)
        if state.step == Step.DECLARE_BLOCKERS and any(move['type'] == 'block' for move in legal):
            return state, attacker, blocker.id, legal
        state = checked_action(state, engine, state.priority_player, {'type': 'pass_priority'})
    pytest.fail('Checked attack did not reach actual defender block declaration')


def resolve_blocks(state, seat, blocks):
    return finish_combat(checked_action(state, RulesEngine(), seat, {'type': 'block', 'blocks': blocks}))


def inspected_decision(state, legal, seat, style):
    before = serialize_match_snapshot(state)
    agent = TraceAgent(style)
    decision = agent.choose_action(state, legal, seat)
    restored = deserialize_match_snapshot(before)
    replay = TraceAgent(style).choose_action(restored, RulesEngine().legal_moves(restored, seat), seat)
    assert serialize_match_snapshot(state) == serialize_match_snapshot(restored) == before
    assert decision.action == replay.action
    view, visible = decision_view(state, seat, legal)
    return decision, agent.forecasts, serialize_match_snapshot(view), visible


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
@pytest.mark.parametrize('style', STYLES)
@pytest.mark.parametrize('case', ['safe', 'lethal_trade'])
def test_profitable_or_current_lethal_block_leaf(seat, family, style, case):
    state, attacker, blocker, legal = defender_position(seat, family, case=case)
    before = serialize_match_snapshot(state)
    decision, forecasts, actor, visible = inspected_decision(state, legal, seat, style)
    blocked = resolve_blocks(state, seat, {attacker: [blocker]})
    unblocked = resolve_blocks(state, seat, {})
    chosen = finish_combat(checked_action(state, RulesEngine(), seat, decision.action))
    assert blocked.players[seat].life == state.players[seat].life and blocked.winner is None
    assert blocked.cards[attacker].zone == Zone.GRAVEYARD
    assert blocked.cards[blocker].zone == (Zone.BATTLEFIELD if case == 'safe' else Zone.GRAVEYARD)
    assert unblocked.players[seat].life == state.players[seat].life - int(ROWS[state.cards[attacker].name]['power'])
    assert unblocked.winner == (3-seat if case == 'lethal_trade' else None)
    # Blocking does not tap mana sources or spend the held interaction.
    assert state.players[seat].hand == blocked.players[seat].hand
    for cid in state.players[seat].battlefield:
        if 'Land' in state.cards[cid].types:
            assert blocked.cards[cid].tapped == state.cards[cid].tapped
    assert serialize_match_snapshot(state) == before
    record(f'{case}-{seat}-{family}-{style}', {'setup': 'funded canonical retained position; checked declaration',
        'seed': 1972639901, 'seat': seat, 'family': family, 'style': style, 'snapshot': before,
        'actor_view': actor, 'legal': legal, 'actor_legal': visible, 'decision': deepcopy(decision.action),
        'reasoning': decision.reasoning, 'forecasts': forecasts,
        'blocked': serialize_match_snapshot(blocked), 'unblocked': serialize_match_snapshot(unblocked),
        'chosen': serialize_match_snapshot(chosen)})
    assert decision.action['type'] == 'block' and chosen.cards[attacker].zone == Zone.GRAVEYARD, (
        f'Missed fully public profitable/lethal-preventing block: {decision.action}; {decision.reasoning}')


def next_checked_attack(state, seat, source):
    engine = RulesEngine()
    for _ in range(100):
        if state.winner is not None:
            return state
        if state.active_player == seat and state.step == Step.DECLARE_ATTACKERS:
            if state.cards[source].zone != Zone.BATTLEFIELD:
                return state
            state = checked_action(state, engine, seat, {'type': 'attack', 'attackers': [source]})
            for _ in range(20):
                if any(move['type'] == 'block' for move in engine.legal_moves(state, 3-seat)):
                    return resolve_blocks(state, 3-seat, {})
                state = checked_action(state, engine, state.priority_player, {'type': 'pass_priority'})
            pytest.fail('Actual next attack did not reach block window')
        state = checked_action(state, engine, state.priority_player, {'type': 'pass_priority'})
    pytest.fail('Actual checked next turn did not reach the retained source attack')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
@pytest.mark.parametrize('style', STYLES)
def test_conditional_race_is_recorded_not_certified_as_hidden_information_win(seat, family, style):
    state, attacker, blocker, legal = defender_position(seat, family, case='race')
    before = serialize_match_snapshot(state)
    decision, forecasts, actor, visible = inspected_decision(state, legal, seat, style)
    blocked = next_checked_attack(resolve_blocks(state, seat, {attacker: [blocker]}), seat, blocker)
    unblocked = next_checked_attack(resolve_blocks(state, seat, {}), seat, blocker)
    chosen_prefix = finish_combat(checked_action(state, RulesEngine(), seat, decision.action))
    assert unblocked.winner == seat and blocked.winner is None
    assert serialize_match_snapshot(state) == before
    record(f'race-{seat}-{family}-{style}', {'classification': 'actual checked no-intervening-play branch; future draw not certified to policy',
        'seed': 1972639901, 'seat': seat, 'family': family, 'style': style, 'snapshot': before,
        'actor_view': actor, 'legal': legal, 'actor_legal': visible, 'decision': deepcopy(decision.action),
        'reasoning': decision.reasoning, 'forecasts': forecasts,
        'blocked_followup': serialize_match_snapshot(blocked), 'unblocked_followup': serialize_match_snapshot(unblocked),
        'chosen_prefix': serialize_match_snapshot(chosen_prefix)})
