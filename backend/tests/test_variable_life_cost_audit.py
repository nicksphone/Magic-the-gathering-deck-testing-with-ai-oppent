"""Real-card boundary for an unsupported variable additional life cost."""

import pytest

from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.ability_model import build_spell_spec
from rules_engine.engine import RulesEngine


def _toxic_deluge_game():
    deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=117)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    spell = CardInstance(
        id="deluge", name="Toxic Deluge", owner=1, controller=1,
        zone=Zone.HAND, types=["Sorcery"], mana_cost="{2}{B}",
        oracle_text="As an additional cost to cast this spell, pay X life.\n"
                    "All creatures get -X/-X until end of turn.",
    )
    state.cards[spell.id] = spell
    state.players[1].hand.append(spell.id)
    state.players[1].mana_pool.update({"B": 1, "C": 2})
    return state, spell


@pytest.mark.xfail(strict=True, reason="Variable additional life costs are not yet parsed or paid")
def test_toxic_deluge_pays_announced_x_life_before_reaching_stack():
    state, spell = _toxic_deluge_game()
    engine = RulesEngine()
    assert any(move.get("card_id") == spell.id and move["type"] == "cast_spell" for move in engine.legal_moves(state, 1))
    state = checked_action(state, engine, 1, {"type": "cast_spell", "card_id": spell.id, "targets": {"x_value": 2}})
    assert state.players[1].life == 18
    assert [item.source_card_id for item in state.stack] == [spell.id]


@pytest.mark.xfail(strict=True, reason="An additional-cost X needs an explicit announced value")
def test_toxic_deluge_cannot_cast_without_announcing_x():
    state, spell = _toxic_deluge_game()
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {"type": "cast_spell", "card_id": spell.id})


@pytest.mark.xfail(strict=True, reason="Name-based effect fallback mistakes Toxic Deluge for a draw spell")
def test_toxic_deluge_does_not_infer_an_unrelated_draw_effect():
    state, spell = _toxic_deluge_game()
    spec = build_spell_spec(state, spell, 1, action_targets={"x_value": 2})
    assert spec.effect.key != "draw_cards"
    assert not spec.used_fallback
