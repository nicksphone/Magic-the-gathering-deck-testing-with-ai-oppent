from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine


def test_activated_target_validation_happens_before_paying_tap_cost():
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}], seed=2)
    state.pregame_pending = False
    state.step = Step.PRECOMBAT_MAIN
    source = CardInstance(id="source", name="Prodigal Pyromancer", owner=1, controller=1, zone=Zone.BATTLEFIELD, types=["Creature"], mana_cost="{2}{R}", power=1, toughness=1, summoning_sick=False, oracle_text="{T}: Prodigal Pyromancer deals 1 damage to any target.")
    state.cards[source.id] = source
    state.players[1].battlefield.append(source.id)
    engine = RulesEngine()
    engine.take_action(state, 1, {"type": "activate_ability", "card_id": source.id, "ability_index": 0, "targets": {"target_player": 99}})
    assert not source.tapped
    assert not state.stack
    engine.take_action(state, 1, {"type": "activate_ability", "card_id": source.id, "ability_index": 0, "targets": {"target_player": 2}})
    assert source.tapped
    assert len(state.stack) == 1


def test_legal_move_card_metadata_is_exposed_only_at_http_boundary():
    import main
    from ai.agent import AIAgent
    deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=3)
    state.pregame_pending = False
    state.step = Step.PRECOMBAT_MAIN
    rules = RulesEngine()
    controller = main.MatchController(state=state, rules=rules, controllers={1: "human", 2: "human"}, ai={1: AIAgent(), 2: AIAgent()}, mode="human_vs_human", deck_ids=(None, None), mainboards={1: deck, 2: deck}, sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False, match_complete=False, best_of=3)
    main.ACTIVE_MATCHES[state.id] = controller
    try:
        assert all("card_view" not in move for move in rules.legal_moves(state, 1))
        move = next(move for move in main.get_legal_moves(state.id, 1)["moves"] if move["type"] == "play_land")
        assert move["card_view"]["name"] == "Island"
    finally:
        main.ACTIVE_MATCHES.pop(state.id, None)


def test_empty_graveyard_target_surface_rejects_stale_card():
    from rules_engine.targeting import validate_cast_targets
    valid, _ = validate_cast_targets({"graveyard_permanent_targets": []}, {"target_card_id": "stale"})
    assert not valid


def test_variable_activation_is_rejected_without_paying_costs():
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}], seed=2)
    state.pregame_pending = False
    state.step = Step.PRECOMBAT_MAIN
    source = CardInstance(id="source", name="Oona, Queen of the Fae", owner=1, controller=1, zone=Zone.BATTLEFIELD, types=["Creature"], summoning_sick=False, oracle_text="{X}{U/B}: Choose a color. Target opponent exiles the top X cards of their library.")
    state.cards[source.id] = source
    state.players[1].battlefield.append(source.id)
    state.players[1].mana_pool["U"] = 4
    RulesEngine().take_action(state, 1, {"type": "activate_ability", "card_id": source.id, "ability_index": 0, "targets": {"target_player": 2, "x_value": 3}})
    assert state.players[1].mana_pool["U"] == 4
    assert not state.stack
    assert "Variable activated costs" in state.log[-1]
    assert not any(move["type"] == "activate_ability" for move in RulesEngine().legal_moves(state, 1))


def test_activated_extractor_preserves_adjacent_mana_symbols():
    from rules_engine.oracle_effects import extract_activated_abilities
    card = CardInstance(id="mage", name="Azure Mage", owner=1, controller=1, zone=Zone.BATTLEFIELD, types=["Creature"], oracle_text="{3}{U}: Draw a card.")
    ability = extract_activated_abilities(card)[0]
    assert ability["mana_cost"] == "{3}{U}"
