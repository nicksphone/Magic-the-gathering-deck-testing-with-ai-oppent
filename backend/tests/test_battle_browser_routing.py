"""Real paid Battle routing from declared birth; browser execution is separate."""
import importlib
import importlib.util

import pytest

from game_state.state import Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine

RULES = RulesEngine()


def advance(state, predicate):
    for _ in range(64):
        if predicate(state):
            return state
        assert state.pending_mechanic_choice is None
        state = checked_action(state, RULES, state.priority_player, {"type": "pass_priority"})
    raise AssertionError("Real Battle transition missed its boundary")


@pytest.mark.parametrize("seat", [1, 2])
@pytest.mark.parametrize("case", ["partial", "player", "blocked"])
def test_real_paid_battle_routing_consequences(seat, case):
    module = "tests.battle_browser_routing_fixture"
    assert importlib.util.find_spec(module) is not None, "Battle routing fixture is missing"
    state, ids = importlib.import_module(module).routing_midgame(seat, blocked=case == "blocked")
    assert len(state.cards) == 120
    assert all(sum(c.owner == pid for c in state.cards.values()) == 60 for pid in (1, 2))
    assert state.delayed_triggers == [] and state.pending_mechanic_choice is None
    state = checked_action(state, RULES, seat, {"type": "cast_spell", "card_id": ids["battle"]})
    state = advance(state, lambda s: s.pending_mechanic_choice is not None)
    choice = state.pending_mechanic_choice
    assert choice["kind"] == "search_library" and choice["player_id"] == seat
    state = checked_action(state, RULES, seat, {"type": "choose_mechanic", "card_ids": choice["options"][:2]})
    state = advance(state, lambda s: s.step == Step.DECLARE_ATTACKERS)
    attacker = ids["attackers"][0]
    target = f"player:{3-seat}" if case == "player" else "battle:" + ids["battle"]
    state = checked_action(state, RULES, seat, {"type": "attack", "attackers": [attacker], "attack_targets": {attacker: target}})
    assert state.attack_targets == {attacker: target}
    state = advance(state, lambda s: s.step == Step.DECLARE_BLOCKERS)
    blocks = {attacker: [ids["blocker"]]} if case == "blocked" else {}
    state = checked_action(state, RULES, 3-seat, {"type": "block", "blocks": blocks})
    state = advance(state, lambda s: s.step == Step.COMBAT_DAMAGE)
    assert state.players[seat].life == 20
    assert state.players[3-seat].life == (18 if case == "player" else 20)
    battle = state.cards[ids["battle"]]
    assert battle.zone == Zone.BATTLEFIELD and battle.counters["defense"] == (1 if case == "partial" else 3)
    assert battle.battle_protector == 3-seat
    assert state.cards[attacker].zone == (Zone.GRAVEYARD if case == "blocked" else Zone.BATTLEFIELD)
    if case == "blocked":
        assert state.cards[ids["blocker"]].zone == Zone.GRAVEYARD
    assert state.pending_mechanic_choice is None
    assert not any(item.effect_key == "battle_defeat" for item in state.stack)
