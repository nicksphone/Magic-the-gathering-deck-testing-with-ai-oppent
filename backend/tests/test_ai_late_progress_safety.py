"""Canonical checked outcomes must not be overridden by an arbitrary turn clock."""
import hashlib
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from game_state.state import MatchFactory, Step, Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine


HERE = Path(__file__).parent / 'fixtures'
ROWS = json.loads((HERE / 'ai_late_progress_safety.json').read_text())
PINS = json.loads((HERE / 'ai_late_progress_safety.provenance.json').read_text())


def position(seat, turn):
    for name, raw in ROWS.items():
        body = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        assert hashlib.sha256(body).hexdigest() == PINS['cards'][name]['canonical_fullrowSHA']
    decks = [[{**ROWS['Forest'], 'card_name': 'Forest', 'quantity': 30},
              {**ROWS[name], 'card_name': name, 'quantity': 1}]
             for name in (['Archangel of Wrath', 'Atraxa, Grand Unifier']
                          if seat == 1 else ['Atraxa, Grand Unifier', 'Archangel of Wrath'])]
    state = MatchFactory.from_decks(*decks, seed=2331)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.DECLARE_ATTACKERS
    state.turn = turn
    for player in state.players.values():
        player.mana_pool.clear()
        for cid in list(player.hand):
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
    for card in state.cards.values():
        if card.name != 'Forest':
            state.players[card.owner].library.remove(card.id)
            card.move_to_zone(Zone.BATTLEFIELD)
            state.players[card.owner].battlefield.append(card.id)
            card.summoning_sick = False
    attacker = next(c.id for c in state.cards.values() if c.name == 'Archangel of Wrath')
    blocker = next(c.id for c in state.cards.values() if c.name == 'Atraxa, Grand Unifier')
    return state, attacker, blocker


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('turn', [19, 20])
def test_clock_does_not_force_a_losing_attack(seat, turn):
    state, attacker, blocker = position(seat, turn)
    rules = RulesEngine()
    before = serialize_match_snapshot(state)
    decision = AIAgent(difficulty='master', archetype='Control').choose_action(
        state, rules.legal_moves(state, seat), seat)
    assert serialize_match_snapshot(state) == before
    branch = checked_action(state, rules, seat, {'type': 'attack', 'attackers': [attacker]})
    for _ in range(24):
        if branch.step == Step.DECLARE_BLOCKERS:
            break
        branch = checked_action(branch, rules, branch.priority_player, {'type': 'pass_priority'})
    assert branch.step == Step.DECLARE_BLOCKERS
    branch = checked_action(branch, rules, 3-seat, {'type': 'block', 'blocks': {attacker: [blocker]}})
    for _ in range(24):
        if branch.step == Step.POSTCOMBAT_MAIN:
            break
        branch = checked_action(branch, rules, branch.priority_player, {'type': 'pass_priority'})
    assert branch.step == Step.POSTCOMBAT_MAIN
    assert branch.cards[attacker].zone == Zone.GRAVEYARD
    assert branch.cards[blocker].zone == Zone.BATTLEFIELD
    assert branch.players[3-seat].life > state.players[3-seat].life
    assert attacker not in decision.action.get('attackers', []), decision.reasoning


@pytest.mark.parametrize('seat', [1, 2])
def test_late_game_still_attacks_when_the_real_blocker_is_tapped(seat):
    state, attacker, blocker = position(seat, 20)
    state.cards[blocker].tapped = True
    before = serialize_match_snapshot(state)
    rules = RulesEngine()
    decision = AIAgent(difficulty='master', archetype='Control').choose_action(
        state, rules.legal_moves(state, seat), seat)
    assert serialize_match_snapshot(state) == before
    assert attacker in decision.action.get('attackers', [])
    branch = checked_action(state, rules, seat, decision.action)
    for _ in range(24):
        if branch.step == Step.DECLARE_BLOCKERS:
            break
        branch = checked_action(branch, rules, branch.priority_player, {'type': 'pass_priority'})
    assert branch.step == Step.DECLARE_BLOCKERS
    branch = checked_action(branch, rules, 3-seat, {'type': 'block', 'blocks': {}})
    for _ in range(24):
        if branch.step == Step.POSTCOMBAT_MAIN:
            break
        branch = checked_action(branch, rules, branch.priority_player, {'type': 'pass_priority'})
    assert branch.step == Step.POSTCOMBAT_MAIN
    assert branch.cards[attacker].zone == Zone.BATTLEFIELD
    assert branch.players[3-seat].life < state.players[3-seat].life
