"""Static player hexproof/shroud affects targets, not untargeted damage."""

import pytest

from ai.agent import AIAgent
from effects.handlers import deal_damage
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.cast_choice import build_cast_hints
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.targeting import validate_hexproof_shroud_targets
from tests.test_api_input_contracts import game, persist, rejected
from tests.test_damage_trigger_targets import _game as damage_trigger_game
from tests.test_divided_damage_resolution import _setup as divided_damage_game


def _game_with_shield(name: str, oracle: str):
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=911)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    shield = CardInstance("shield", name, 2, 2, Zone.BATTLEFIELD, ["Enchantment"], oracle_text=oracle)
    bolt = CardInstance("bolt", "Shock", 1, 1, Zone.HAND, ["Instant"], mana_cost="{R}", oracle_text="Shock deals 2 damage to any target.")
    state.cards.update({shield.id: shield, bolt.id: bolt})
    state.players[2].battlefield.append(shield.id)
    state.players[1].hand.append(bolt.id)
    state.players[1].mana_pool["R"] = 1
    return state, bolt


def test_leyline_filters_opponent_player_but_allows_controller_and_untargeted_damage():
    state, bolt = _game_with_shield(
        "Leyline of Sanctity",
        "If this card is in your opening hand, you may begin the game with it on the battlefield.\nYou have hexproof.",
    )
    assert not validate_hexproof_shroud_targets(state, 1, {"target_player": 2})[0]
    assert validate_hexproof_shroud_targets(state, 2, {"target_player": 2})[0]
    assert {target["id"] for target in build_cast_hints(state, bolt, 1)["player_targets"]} == {1}
    assert not validate_hexproof_shroud_targets(state, 1, {"target_distribution": {"2": 2}})[0]
    deal_damage(state, 1, {"target_player": 2, "amount": 2})
    assert state.players[2].life == 18


def test_ivory_mask_shroud_blocks_both_players_from_targeting_its_controller():
    state, bolt = _game_with_shield("Ivory Mask", "You have shroud.")
    assert not validate_hexproof_shroud_targets(state, 1, {"target_player": 2})[0]
    assert not validate_hexproof_shroud_targets(state, 2, {"target_player": 2})[0]
    assert {target["id"] for target in build_cast_hints(state, bolt, 1)["player_targets"]} == {1}


def test_trigger_options_and_resolution_recheck_player_hexproof():
    state = damage_trigger_game()
    shield = CardInstance("shield", "Aegis of the Gods", 2, 2, Zone.BATTLEFIELD, ["Creature", "Enchantment"], oracle_text="You have hexproof.", power=2, toughness=1)
    state.cards[shield.id] = shield
    state.players[2].battlefield.append(shield.id)
    rules = RulesEngine()
    assert 2 not in {move.get("target_player") for move in rules.legal_moves(state, 1)}
    assert 1 in {move.get("target_player") for move in rules.legal_moves(state, 1)}

    state.players[2].battlefield.remove(shield.id)
    shield.zone = Zone.HAND
    state.players[2].hand.append(shield.id)
    state = checked_action(state, rules, 1, {
        "type": "choose_trigger_target", "stack_id": state.stack[-1].id, "target_player": 2,
    })
    state.players[2].hand.remove(shield.id)
    shield.zone = Zone.BATTLEFIELD
    state.players[2].battlefield.append(shield.id)
    assert resolve_top_of_stack(state)
    assert state.players[2].life == 20
    assert any("does not resolve" in line for line in state.log)


def test_cast_target_becomes_illegal_when_player_gains_hexproof():
    state, bolt = _game_with_shield("Leyline of Sanctity", "You have hexproof.")
    state.players[2].battlefield.remove("shield")
    state.players[2].hand.append("shield")
    state.cards["shield"].zone = Zone.HAND
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": bolt.id, "targets": {"target_player": 2},
    })
    state.players[2].hand.remove("shield")
    state.players[2].battlefield.append("shield")
    state.cards["shield"].zone = Zone.BATTLEFIELD
    assert resolve_top_of_stack(state)
    assert state.players[2].life == 20


def test_hexproof_player_is_missing_from_http_hints_and_rejected_without_mutation(game):
    client, match = game
    state = match.state
    shield = CardInstance("shield", "Leyline of Sanctity", 2, 2, Zone.BATTLEFIELD, ["Enchantment"], oracle_text="You have hexproof.")
    bolt = CardInstance("bolt", "Shock", 1, 1, Zone.HAND, ["Instant"], mana_cost="{R}", oracle_text="Shock deals 2 damage to any target.")
    state.cards.update({shield.id: shield, bolt.id: bolt})
    state.players[2].battlefield.append(shield.id)
    state.players[1].hand.append(bolt.id)
    state.players[1].mana_pool["R"] = 1
    persist(match)
    moves = client.get(f"/matches/{state.id}/legal-moves").json()["moves"]
    cast = next(move for move in moves if move.get("card_id") == bolt.id and move["type"] == "cast_spell")
    assert {target["id"] for target in cast["target_hints"]["player_targets"]} == {1}
    rejected(client, match, {"type": "cast_spell", "card_id": bolt.id, "targets": {"target_player": 2}})


def test_divided_damage_omits_newly_hexproof_player_but_keeps_creature_share():
    state = divided_damage_game()
    action = {"type": "cast_spell", "card_id": "pyrotechnics", "targets": {"target_distribution": {"first": 1, "2": 3}}}
    shield = CardInstance("shield", "Leyline of Sanctity", 2, 2, Zone.BATTLEFIELD, ["Enchantment"], oracle_text="You have hexproof.")
    state.cards[shield.id] = shield
    state.players[2].battlefield.append(shield.id)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, action)
    state.players[2].battlefield.remove(shield.id)
    shield.zone = Zone.HAND
    state.players[2].hand.append(shield.id)
    state = checked_action(state, RulesEngine(), 1, action)
    state.players[2].hand.remove(shield.id)
    shield.zone = Zone.BATTLEFIELD
    state.players[2].battlefield.append(shield.id)
    assert resolve_top_of_stack(state)
    assert state.players[2].life == 20
    assert state.cards["first"].counters.get("__damage_marked", 0) == 1


@pytest.mark.parametrize("name, oracle", [
    ("Shock", "Shock deals 2 damage to any target."),
    ("Lightning Bolt", "Lightning Bolt deals 3 damage to any target."),
])
def test_ai_does_not_choose_protected_opponent_for_burn_spell(name, oracle):
    state, bolt = _game_with_shield("Leyline of Sanctity", "You have hexproof.")
    bolt.name = name
    bolt.oracle_text = oracle
    state.players[1].hand = [bolt.id]
    moves = RulesEngine().legal_moves(state, 1)
    cast = next(move for move in moves if move.get("card_id") == bolt.id and move["type"] == "cast_spell")
    agent = AIAgent(difficulty="master", archetype="Burn")
    materialized = agent._materialize_action(state, cast, 1)
    assert materialized.get("targets", {}).get("target_player") != 2
    assert agent.choose_action(state, moves, 1).action["type"] != "cast_spell"


def test_ai_can_burn_opposing_creature_behind_player_hexproof():
    state, bolt = _game_with_shield("Leyline of Sanctity", "You have hexproof.")
    state.players[1].hand = [bolt.id]
    bear = CardInstance("bear", "Grizzly Bears", 2, 2, Zone.BATTLEFIELD, ["Creature"], power=2, toughness=2)
    state.cards[bear.id] = bear
    state.players[2].battlefield.append(bear.id)
    moves = RulesEngine().legal_moves(state, 1)
    cast = next(move for move in moves if move.get("card_id") == bolt.id and move["type"] == "cast_spell")
    agent = AIAgent(difficulty="master", archetype="Burn")
    assert not agent._burn_has_only_friendly_targets(state, cast, 1)
    materialized = agent._materialize_action(state, cast, 1)
    assert materialized["targets"]["target_card_id"] == bear.id
    assert materialized["targets"].get("target_player") is None


@pytest.mark.parametrize("defense", ["hexproof", "shroud", "protection from red"])
def test_battlefield_target_hints_omit_defended_creature(defense):
    state, bolt = _game_with_shield("Leyline of Sanctity", "You have hexproof.")
    state.players[1].hand = [bolt.id]
    bear = CardInstance("bear", "Grizzly Bears", 2, 2, Zone.BATTLEFIELD, ["Creature"], power=2, toughness=2, keywords=[defense])
    state.cards[bear.id] = bear
    state.players[2].battlefield.append(bear.id)
    moves = RulesEngine().legal_moves(state, 1)
    cast = next(move for move in moves if move.get("card_id") == bolt.id and move["type"] == "cast_spell")
    assert bear.id not in {target["id"] for target in cast["target_hints"]["creature_targets"]}
    assert AIAgent(difficulty="master", archetype="Burn").choose_action(state, moves, 1).action["type"] != "cast_spell"
