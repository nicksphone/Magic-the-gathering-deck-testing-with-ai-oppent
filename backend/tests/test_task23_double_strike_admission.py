"""Effective old-board double-strike grant; actual checked combat, no paid grant claim."""
import pytest
from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from rules_engine.engine import RulesEngine
from rules_engine.keyword_effects import add_keyword_effect
from tests.test_task23_canonical_block_outcomes import position, blocked, Zone

@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['strong', 'master'])
def test_real_double_strike_damage_is_not_screened_as_one_power_step(seat, difficulty):
    root, attacker, cheap, large, _ = position(seat, trample=True)
    add_keyword_effect(root, attacker, ['double strike'])
    root.players[seat].life = 13
    before = serialize_match_snapshot(root)
    surviving = blocked(root, seat, attacker, [cheap, large])
    assert surviving.players[seat].life == 1
    assert surviving.winner is None
    assert all(surviving.cards[cid].zone == Zone.GRAVEYARD for cid in (cheap, large))
    single = blocked(root, seat, attacker, [cheap])
    assert single.winner == 3 - seat
    action = AIAgent(difficulty=difficulty).choose_action(root, RulesEngine().legal_moves(root, seat), seat).action
    result = blocked(root, seat, attacker, (action.get('blocks') or {}).get(attacker) or [])
    assert serialize_match_snapshot(root) == before
    assert result.winner != 3 - seat, 'Full double-strike combat has a checked surviving legal plan'
