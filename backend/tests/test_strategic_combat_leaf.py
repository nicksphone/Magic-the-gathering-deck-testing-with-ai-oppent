"""Complete public outcomes versus the unchanged speculative-combat boundary."""
import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_empty_hand_attack_witness import ROWS, position
from tests.test_linked_damage_targets import raw_card


class PrefixOnlyAgent(AIAgent):
    def _complete_strategic_combat_leaf(self, state, player_id):
        return None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('creature', ['Sheoldred, the Apocalypse', 'Torrential Gearhulk'])
@pytest.mark.parametrize('lethal', [False, True])
def test_completed_leaf_counts_actual_damage_once(seat, creature, lethal):
    state, source = position(seat, creature, opponent_life=int(ROWS[creature]['power']) if lethal else 20)
    engine = RulesEngine()
    agent = AIAgent(difficulty='master')
    move = {'type': 'attack', 'attackers': [source]}
    before = serialize_match_snapshot(state)
    announced = checked_action(state, engine, seat, move)
    outcome = agent._complete_strategic_combat_leaf(announced, seat)
    assert outcome is not None
    assert outcome.players[3-seat].life == state.players[3-seat].life - int(ROWS[creature]['power'])
    assert outcome.winner == (seat if lethal else None)
    actual = agent._strategic_position_score(outcome, seat)
    assert agent._strategic_line_score(state, move, seat, 2) == pytest.approx(
        actual + agent._instant_value_reservation(state, move, seat))
    prefix = agent._strategic_position_score(announced, seat)
    assert agent._strategic_state_score(announced, seat, 0, prefix + 7) == pytest.approx(actual + 7)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('creature', ['Sheoldred, the Apocalypse', 'Torrential Gearhulk'])
def test_tapped_basic_acceptance_supersedes_old_pass_characterization(seat, creature):
    state, source = position(seat, creature, tapped_lands=True)
    before = serialize_match_snapshot(state)
    engine = RulesEngine()
    decision = AIAgent(difficulty='master', archetype='Control', opponent_archetype='Aggro').choose_action(
        state, engine.legal_moves(state, seat), seat)
    assert decision.action['type'] == 'attack' and source in decision.action['attackers']
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('boundary', ['hand', 'graveyard', 'exile', 'blocker', 'nonbasic', 'unannounced'])
def test_unknown_or_adverse_boundary_keeps_original_prefix_score(seat, boundary):
    state, source = position(seat, 'Sheoldred, the Apocalypse')
    if boundary in {'hand', 'graveyard', 'exile'}:
        raw_card(state, ROWS['Lightning Bolt'], 3-seat, getattr(Zone, boundary.upper()))
    elif boundary == 'blocker':
        raw_card(state, ROWS['Monastery Swiftspear'], 3-seat, Zone.BATTLEFIELD)
    elif boundary == 'nonbasic':
        raw_card(state, ROWS['Mutavault'], 3-seat, Zone.BATTLEFIELD)
    before = serialize_match_snapshot(state)
    engine = RulesEngine()
    move = {'type': 'attack', 'attackers': [source]}
    announced = state if boundary == 'unannounced' else checked_action(state, engine, seat, move)
    agent = AIAgent(difficulty='master')
    assert agent._complete_strategic_combat_leaf(announced, seat) is None
    if boundary != 'unannounced':
        original = PrefixOnlyAgent(difficulty='master')
        assert agent._strategic_line_score(state, move, seat, 0) == pytest.approx(
            original._strategic_line_score(state, move, seat, 0))
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_bolt_and_counterspell_preserve_response_windows(seat):
    state, source = position(seat, 'Sheoldred, the Apocalypse', counter=True)
    bolt = raw_card(state, ROWS['Lightning Bolt'], 3-seat, Zone.HAND)
    counter = next(cid for cid in state.players[seat].hand if state.cards[cid].name == 'Counterspell')
    before = serialize_match_snapshot(state)
    engine = RulesEngine()
    agent = AIAgent(difficulty='master')
    announced = checked_action(state, engine, seat, {'type': 'attack', 'attackers': [source]})
    assert agent._complete_strategic_combat_leaf(announced, seat) is None
    reply = checked_action(announced, engine, seat, {'type': 'pass_priority'})
    paid = checked_action(reply, engine, 3-seat, {'type': 'cast_spell', 'card_id': bolt.id,
        'targets': {'target_card_id': source}})
    assert paid.stack and any(paid.cards[cid].tapped for cid in paid.players[3-seat].battlefield)
    assert agent._complete_strategic_combat_leaf(paid, seat) is None
    offered = checked_action(paid, engine, 3-seat, {'type': 'pass_priority'})
    assert any(move['type'] == 'cast_spell' and move.get('card_id') == counter
               for move in engine.legal_moves(offered, seat))
    answered = checked_action(offered, engine, seat, {'type': 'cast_spell', 'card_id': counter,
        'targets': {'target_stack_id': offered.stack[-1].id}})
    assert len(answered.stack) == 2
    assert agent._complete_strategic_combat_leaf(answered, seat) is None
    assert serialize_match_snapshot(state) == before
