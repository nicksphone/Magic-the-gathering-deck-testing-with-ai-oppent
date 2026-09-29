"""Variable additional-life costs and all-creatures temporary debuffs."""

import pytest

from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.ability_model import build_spell_spec
from rules_engine.cast_choice import build_cast_hints
from rules_engine.continuous import effective_toughness
from rules_engine.costs import check_cost_option_available, collect_cost_options
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.state_based_actions import apply_state_based_actions
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from ai.agent import AIAgent


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


def test_toxic_deluge_pays_announced_x_life_before_reaching_stack():
    state, spell = _toxic_deluge_game()
    engine = RulesEngine()
    assert any(move.get("card_id") == spell.id and move["type"] == "cast_spell" for move in engine.legal_moves(state, 1))
    state = checked_action(state, engine, 1, {"type": "cast_spell", "card_id": spell.id, "targets": {"x_value": 2}})
    assert state.players[1].life == 18
    assert [item.source_card_id for item in state.stack] == [spell.id]
    assert any("pays 2 life" in line for line in state.log)


def test_toxic_deluge_cannot_cast_without_announcing_x():
    state, spell = _toxic_deluge_game()
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {"type": "cast_spell", "card_id": spell.id})
    assert state.players[1].life == 20 and spell.id in state.players[1].hand


def test_toxic_deluge_does_not_infer_an_unrelated_draw_effect():
    state, spell = _toxic_deluge_game()
    spec = build_spell_spec(state, spell, 1, action_targets={"x_value": 2})
    assert spec.effect.key == "temporary_pt_buff_all"
    assert spec.effect.payload == {"power": -2, "toughness": -2}
    assert not spec.used_fallback


def _creature(state, player, cid, toughness):
    card = CardInstance(id=cid, name=cid, owner=player, controller=player,
                        zone=Zone.BATTLEFIELD, types=["Creature"], power=toughness, toughness=toughness)
    state.cards[cid] = card
    state.players[player].battlefield.append(cid)
    return card


def test_x_life_is_checked_before_payment_and_all_creatures_are_affected():
    state, spell = _toxic_deluge_game()
    _creature(state, 1, "own-three", 3)
    _creature(state, 2, "their-two", 2)
    _creature(state, 2, "their-four", 4)
    hints = build_cast_hints(state, spell, 1)
    assert hints["requires_x_value"] and hints["x_value_max"] == 20
    option = collect_cost_options(state, 1, spell)[0]
    assert option.pay_life_x and option.pay_life == 0
    for x in (-1, 21):
        assert not check_cost_option_available(state, 1, spell, option, x_value=x)
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), 1, {"type": "cast_spell", "card_id": spell.id, "targets": {"x_value": x}})
    assert state.players[1].life == 20 and spell.id in state.players[1].hand

    state = checked_action(state, RulesEngine(), 1, {"type": "cast_spell", "card_id": spell.id, "targets": {"x_value": 2}})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(state)
    assert effective_toughness(state, "own-three") == 1
    assert effective_toughness(state, "their-two") == 0
    assert effective_toughness(state, "their-four") == 2
    apply_state_based_actions(state)
    assert "their-two" in state.players[2].graveyard
    assert "own-three" in state.players[1].battlefield
    _creature(state, 2, "late-two", 2)
    assert effective_toughness(state, "late-two") == 2
    RulesEngine()._clear_marked_damage(state)
    assert effective_toughness(state, "own-three") == 3
    assert effective_toughness(state, "their-four") == 4


def test_zero_x_is_legal_and_does_not_pay_life():
    state, spell = _toxic_deluge_game()
    state = checked_action(state, RulesEngine(), 1, {"type": "cast_spell", "card_id": spell.id, "targets": {"x_value": 0}})
    assert state.players[1].life == 20
    assert not any("pays 0 life" in line for line in state.log)


def test_variable_life_payment_trigger_is_above_spell():
    state, spell = _toxic_deluge_game()
    font = CardInstance(id="font", name="Font of Agonies", owner=1, controller=1,
                        zone=Zone.BATTLEFIELD, types=["Enchantment"],
                        oracle_text="Whenever you pay life, put that many blood counters on this enchantment.")
    state.cards[font.id] = font
    state.players[1].battlefield.append(font.id)
    state = checked_action(state, RulesEngine(), 1, {"type": "cast_spell", "card_id": spell.id, "targets": {"x_value": 2}})
    assert [item.source_card_id for item in state.stack] == [spell.id, font.id]
    assert resolve_top_of_stack(state)
    assert state.cards[font.id].counters.get("blood") == 2


def test_life_total_lock_allows_zero_x_but_not_positive_x():
    state, spell = _toxic_deluge_game()
    lock = CardInstance(id="lock", name="Platinum Emperion", owner=1, controller=1,
                        zone=Zone.BATTLEFIELD, types=["Artifact", "Creature"], power=8, toughness=8,
                        oracle_text="Your life total can't change.")
    state.cards[lock.id] = lock
    state.players[1].battlefield.append(lock.id)
    assert build_cast_hints(state, spell, 1)["x_value_max"] == 0
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {"type": "cast_spell", "card_id": spell.id, "targets": {"x_value": 1}})
    state = checked_action(state, RulesEngine(), 1, {"type": "cast_spell", "card_id": spell.id, "targets": {"x_value": 0}})
    assert state.players[1].life == 20


def test_oracle_text_prevents_name_guess_for_other_collision():
    state, spell = _toxic_deluge_game()
    spell.name = "Shockingly Complex"
    spell.oracle_text = "Choose a card name."
    spec = build_spell_spec(state, spell, 1)
    assert spec.effect.key == "noop" and spec.used_fallback


def test_ai_selects_board_useful_life_x_not_all_available_life():
    state, spell = _toxic_deluge_game()
    _creature(state, 1, "own-four", 4)
    _creature(state, 2, "their-two", 2)
    agent = AIAgent(archetype="Control")
    assert agent._choose_variable_life_x(state, 1, spell) == 2
    move = next(move for move in RulesEngine().legal_moves(state, 1)
                if move.get("card_id") == spell.id and move["type"] == "cast_spell")
    action = agent._materialize_action(state, move, 1)
    assert action["targets"]["x_value"] == 2
    assert not action.get("_invalid_ai_choice")
    state.players[2].battlefield.clear()
    assert agent._choose_variable_life_x(state, 1, spell) == 0
