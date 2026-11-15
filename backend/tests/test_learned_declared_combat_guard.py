"""Proposed opt-in combat horizon: ten canonical, actor-view cases.

Full RAW reaches Factory through the existing canonical position helper.
Physical battlefield/life/phase poses are declared fixtures, not played games.
No fitted checkpoint, fabricated Oracle/StackItem, or forced choice is used.
"""
from copy import deepcopy
import json

import pytest

from ai.action_contract import complete_action
from ai.information import decision_view
from ai.pending_effects import unanswered_action_loses, unanswered_action_wins
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_ai_strategy_fundamentals import position
from tests.test_learned_tactical_guard import _cast, _route


RULES = RulesEngine()


def _pending(state):
    return (state.pending_mechanic_choice or state.pending_replacement_choice
            or state.pending_trigger_order)


def _declared_combat(seat, *, observers=0, response=False):
    state, _, enemies, move = position(seat,
        ['Lightning Bolt'] if response else [], ['Mountain'] if response else [],
        enemy=['Grizzly Bears'],
        reserve=['Grizzly Bears'] + ['Grim Haruspex'] * observers)
    blocker = move('Grizzly Bears', seat, Zone.BATTLEFIELD)
    for _ in range(observers):
        move('Grim Haruspex', seat, Zone.BATTLEFIELD)
    attacker = enemies['Grizzly Bears']
    state.players[seat].life = 2
    state.active_player = state.priority_player = 3-seat
    state.step = Step.DECLARE_ATTACKERS
    state.passed_priority.clear()
    state.mechanic_choice_players = {1, 2}
    state.replacement_choice_players = {1, 2}
    state.trigger_order_choice_players = {1, 2}
    state.trigger_order_choice_required = True
    state = checked_action(state, RULES, 3-seat,
                            {'type': 'attack', 'attackers': [attacker]})
    assert state.attackers == [attacker] and state.cards[attacker].tapped
    for _ in range(4):
        assert not _pending(state), 'Never choose for either player'
        if state.step == Step.DECLARE_BLOCKERS:
            break
        state = checked_action(state, RULES, state.priority_player,
                               {'type': 'pass_priority'})
    assert state.step == Step.DECLARE_BLOCKERS and state.priority_player == seat
    assert not state.blockers_declared
    block = complete_action({'type': 'block', 'blocks': {attacker: [blocker]}})
    return state, attacker, blocker, block


def _core_finish(state):
    """Genuine checked passes only; stop BEFORE any unresolved choice."""
    for _ in range(16):
        if _pending(state) or state.winner is not None or state.step == Step.END_COMBAT:
            return state
        state = checked_action(state, RULES, state.priority_player,
                               {'type': 'pass_priority'})
    raise AssertionError('Actual combat exceeded sixteen checked passes')


def _view(state, seat):
    return decision_view(state, seat, RULES.legal_moves(deepcopy(state), seat))[0]


@pytest.mark.parametrize('seat', [1, 2])
def test_default_forecasts_keep_original_empty_stack_horizon(seat):
    state, _, _, block = _declared_combat(seat)
    before = serialize_match_snapshot(state)
    view = _view(state, seat)
    view_before = serialize_match_snapshot(view)
    for action in ({'type': 'pass_priority'}, block):
        assert unanswered_action_wins(view, seat, action) is False
        assert unanswered_action_loses(view, seat, action) is False
    assert serialize_match_snapshot(view) == view_before
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_opt_in_checked_combat_prefers_surviving_block(monkeypatch, tmp_path, seat):
    state, attacker, blocker, block = _declared_combat(seat)
    before = serialize_match_snapshot(state)
    wait = {'type': 'pass_priority'}
    passed = _core_finish(checked_action(state, RULES, seat, wait))
    defended = _core_finish(checked_action(state, RULES, seat, block))
    assert not _pending(passed) and not _pending(defended)
    assert passed.winner == 3-seat and passed.players[seat].life == 0
    assert defended.winner is None and defended.step == Step.END_COMBAT
    assert defended.players[seat].life == 2
    assert defended.cards[attacker].zone == defended.cards[blocker].zone == Zone.GRAVEYARD
    view = _view(state, seat)
    view_before = serialize_match_snapshot(view)
    assert unanswered_action_wins(view, seat, wait, settle_declared_combat=True) is False
    assert unanswered_action_loses(view, seat, wait, settle_declared_combat=True) is True
    assert unanswered_action_wins(view, seat, block, settle_declared_combat=True) is False
    assert unanswered_action_loses(view, seat, block, settle_declared_combat=True) is False
    assert serialize_match_snapshot(view) == view_before
    action, calls = _route(monkeypatch, state, seat, [wait, block],
                           {'pass_priority': 0.9, 'block': -0.9})
    assert calls['scored'] == ['pass_priority', 'block']
    assert serialize_match_snapshot(state) == before
    (tmp_path / 'checked-combat.json').write_text(json.dumps(dict(
        seat=seat, synthetic_q=True, pass_winner=passed.winner,
        block_winner=defended.winner, block_life=defended.players[seat].life,
        block_step=defended.step.value, selected_type=action.get('type') if action else None)))
    assert action == block, 'Synthetic-Q protocol: actual blocking survives; no-block loses'


@pytest.mark.parametrize('seat', [1, 2])
def test_opt_in_real_simultaneous_death_triggers_remain_unknown(seat):
    # Two real Haruspices observe one real nontoken death: mandatory order choice.
    state, _, blocker, block = _declared_combat(seat, observers=2)
    before = serialize_match_snapshot(state)
    branch = _core_finish(checked_action(state, RULES, seat, block))
    assert branch.cards[blocker].zone == Zone.GRAVEYARD
    assert branch.pending_trigger_order
    assert branch.pending_trigger_order['current_controller'] == seat
    assert len(branch.pending_trigger_order['groups'][str(seat)]) == 2
    assert branch.players[seat].library == state.players[seat].library
    assert branch.players[seat].hand == state.players[seat].hand
    view = _view(state, seat)
    view_before = serialize_match_snapshot(view)
    assert unanswered_action_wins(view, seat, block, settle_declared_combat=True) is None
    assert unanswered_action_loses(view, seat, block, settle_declared_combat=True) is None
    assert serialize_match_snapshot(view) == view_before
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_opt_in_real_death_draw_hidden_zone_change_remains_unknown(seat):
    # One mandatory Haruspex draw has no choice, but changes the opaque library.
    state, _, blocker, block = _declared_combat(seat, observers=1)
    before = serialize_match_snapshot(state)
    branch = _core_finish(checked_action(state, RULES, seat, block))
    assert branch.cards[blocker].zone == Zone.GRAVEYARD
    assert not _pending(branch) and branch.step == Step.END_COMBAT
    assert len(branch.players[seat].library) == len(state.players[seat].library) - 1
    assert len(branch.players[seat].hand) == len(state.players[seat].hand) + 1
    view = _view(state, seat)
    view_before = serialize_match_snapshot(view)
    assert unanswered_action_wins(view, seat, block, settle_declared_combat=True) is None
    assert unanswered_action_loses(view, seat, block, settle_declared_combat=True) is None
    assert serialize_match_snapshot(view) == view_before
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_opt_in_does_not_pass_away_a_known_future_response(seat):
    state, attacker, _, _ = _declared_combat(seat, response=True)
    before = serialize_match_snapshot(state)
    wait = {'type': 'pass_priority'}
    unblocked = checked_action(state, RULES, seat, wait)
    assert unblocked.blockers_declared and not unblocked.blocks
    assert unblocked.step == Step.DECLARE_BLOCKERS
    assert unblocked.priority_player == 3-seat
    # Conditional all-pass loses, but is NOT the actor's only actual continuation.
    missed_response = _core_finish(unblocked)
    assert missed_response.winner == 3-seat
    offered = checked_action(unblocked, RULES, 3-seat, wait)
    assert offered.step == Step.DECLARE_BLOCKERS and offered.priority_player == seat
    bolt_id = next(cid for cid in offered.players[seat].hand
                   if offered.cards[cid].name == 'Lightning Bolt')
    assert any(move['type'] == 'cast_spell' and move.get('card_id') == bolt_id
               for move in RULES.legal_moves(deepcopy(offered), seat))
    bolt = _cast(offered, {'Lightning Bolt': bolt_id}, seat, 'Lightning Bolt',
                 {'target_card_id': attacker})
    answered = _core_finish(checked_action(offered, RULES, seat, bolt))
    assert not _pending(answered) and answered.step == Step.END_COMBAT
    assert answered.winner is None and answered.players[seat].life == 2
    assert answered.cards[attacker].zone == answered.cards[bolt_id].zone == Zone.GRAVEYARD
    assert any(answered.cards[cid].tapped for cid in answered.players[seat].battlefield
               if 'Land' in answered.cards[cid].types)
    view = _view(state, seat)
    view_before = serialize_match_snapshot(view)
    assert unanswered_action_wins(view, seat, wait, settle_declared_combat=True) is None
    assert unanswered_action_loses(view, seat, wait, settle_declared_combat=True) is None
    assert serialize_match_snapshot(view) == view_before
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_uncertified_critical_combat_defers_to_heuristic(monkeypatch, seat):
    state, _, _, block = _declared_combat(seat, response=True)
    before = serialize_match_snapshot(state)
    action, calls = _route(monkeypatch, state, seat,
                           [{'type': 'pass_priority'}, block],
                           {'pass_priority': 0.9, 'block': -0.9})
    assert calls['scored'] == ['pass_priority', 'block']
    assert serialize_match_snapshot(state) == before
    assert action is None, 'Unknown critical combat must use the existing heuristic fallback'


@pytest.mark.parametrize('seat', [1, 2])
def test_unsupported_negative_is_refused_before_last_chance_pass(seat):
    from rules_engine.combat_constraints import combat_rule_view

    state, attacker, _, _ = _declared_combat(seat)
    wait = {'type': 'pass_priority'}
    state = checked_action(state, RULES, seat, wait)
    state = checked_action(state, RULES, 3-seat, wait)
    assert state.blockers_declared and not state.stack
    assert state.priority_player == seat and 3-seat in state.passed_priority
    assert checked_action(state, RULES, seat, wait).winner == 3-seat
    # Explicit parser-negative vector, NOT authentic Grizzly Bears Oracle text.
    state.cards[attacker].oracle_text = "As long as an unknown condition, this creature can't be blocked."
    assert combat_rule_view(state, attacker)['unsupported']
    before = serialize_match_snapshot(state)
    view = _view(state, seat)
    assert unanswered_action_wins(view, seat, wait, settle_declared_combat=True) is None
    assert unanswered_action_loses(view, seat, wait, settle_declared_combat=True) is None
    assert serialize_match_snapshot(state) == before
