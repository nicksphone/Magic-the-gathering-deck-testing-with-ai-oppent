from ai.agent import AIAgent
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine


def state_with_targets():
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}], seed=3)
    state.pregame_pending = False
    state.step = Step.PRECOMBAT_MAIN
    for cid, name, power, owner in (("friendly", "Phantom Nishoba", 7, 1), ("enemy", "Grizzly Bears", 2, 2)):
        state.cards[cid] = CardInstance(id=cid, name=name, owner=owner, controller=owner, zone=Zone.BATTLEFIELD, types=["Creature"], power=power, toughness=power, summoning_sick=False)
        state.players[owner].battlefield.append(cid)
    return state


def test_ai_uses_the_fixed_damage_budget_and_an_enemy_recipient():
    state = state_with_targets()
    card = CardInstance(id="spell", name="Pyrotechnics", owner=1, controller=1, zone=Zone.HAND, types=["Sorcery"], mana_cost="{4}{R}", oracle_text="Pyrotechnics deals 4 damage divided as you choose among any number of targets.")
    state.cards[card.id] = card
    state.players[1].hand.append(card.id)
    state.players[1].mana_pool["R"] = 5
    engine = RulesEngine()
    move = next(move for move in engine.legal_moves(state, 1) if move.get("card_id") == card.id and move["type"] == "cast_spell")
    action = AIAgent()._materialize_action(state, move, 1)
    assert action["targets"]["target_distribution"] == {"enemy": 4}
    engine.take_action(state, 1, action, reject_invalid=True)
    assert state.stack[-1].payload["target_distribution"] == {"enemy": 4}


def test_generic_targeted_activation_gets_a_materialized_enemy_target():
    state = state_with_targets()
    state.cards["enemy"].counters["__damage_marked"] = 1
    source = CardInstance(id="pyro", name="Prodigal Pyromancer", owner=1, controller=1, zone=Zone.BATTLEFIELD, types=["Creature"], power=1, toughness=1, summoning_sick=False, oracle_text="{T}: Prodigal Pyromancer deals 1 damage to any target.")
    state.cards[source.id] = source
    state.players[1].battlefield.append(source.id)
    engine = RulesEngine()
    move = next(move for move in engine.legal_moves(state, 1) if move.get("card_id") == source.id and move["type"] == "activate_ability")
    action = AIAgent()._materialize_action(state, move, 1)
    assert action["targets"]["target_card_id"] == "enemy"
    engine.take_action(state, 1, action, reject_invalid=True)
    assert source.tapped
    assert state.stack[-1].payload["target_card_id"] == "enemy"


def test_generic_targeted_activation_avoids_nonlethal_creature_damage():
    state = state_with_targets()
    source = CardInstance(id="pyro", name="Prodigal Pyromancer", owner=1, controller=1, zone=Zone.BATTLEFIELD, types=["Creature"], power=1, toughness=1, summoning_sick=False, oracle_text="{T}: Prodigal Pyromancer deals 1 damage to any target.")
    state.cards[source.id] = source
    state.players[1].battlefield.append(source.id)
    engine = RulesEngine()
    move = next(move for move in engine.legal_moves(state, 1) if move.get("card_id") == source.id and move["type"] == "activate_ability")
    action = AIAgent()._materialize_action(state, move, 1)
    assert action["targets"] == {"target_player": 2}
    engine.take_action(state, 1, action, reject_invalid=True)
    assert state.stack[-1].payload["target_player"] == 2
