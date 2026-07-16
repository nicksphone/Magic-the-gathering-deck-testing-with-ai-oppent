from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine.cycling import cycling_variant


def _state_with_cycler() -> tuple[object, str]:
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}])
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    state.players[1].battlefield.append("land-1")
    state.cards["land-1"] = CardInstance(
        id="land-1", name="Island", owner=1, controller=1, zone=Zone.BATTLEFIELD, types=["Land"]
    )
    cid = "cycler"
    state.cards[cid] = CardInstance(
        id=cid,
        name="Lonely Sandbar",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Land"],
        oracle_text="Cycling {1}",
    )
    state.players[1].hand.append(cid)
    return state, cid


def test_fixed_cycling_is_a_legal_hand_action() -> None:
    state, cid = _state_with_cycler()
    moves = RulesEngine().legal_moves(state, 1)
    assert any(m["type"] == "cycle_card" and m["card_id"] == cid for m in moves)


def test_cycling_pays_cost_discards_then_draws_on_resolution() -> None:
    state, cid = _state_with_cycler()
    engine = RulesEngine()
    before_hand = len(state.players[1].hand)
    engine.take_action(state, 1, {"type": "cycle_card", "card_id": cid})
    assert cid in state.players[1].graveyard
    assert cid not in state.players[1].hand
    assert len(state.players[1].hand) == before_hand - 1
    assert state.stack
    engine.take_action(state, 1, {"type": "pass_priority"})
    engine.take_action(state, 2, {"type": "pass_priority"})
    assert not state.stack
    assert len(state.players[1].hand) == before_hand


def test_cycling_trigger_is_matched_by_card_name_and_put_above_ability() -> None:
    state, cid = _state_with_cycler()
    source_id = "cycling-payoff"
    state.cards[source_id] = CardInstance(
        id=source_id,
        name="Cycling Payoff",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="When you cycle Lonely Sandbar, draw a card.",
    )
    state.players[1].battlefield.append(source_id)
    engine = RulesEngine()
    engine.take_action(state, 1, {"type": "cycle_card", "card_id": cid})
    assert [item.effect_key for item in state.stack] == ["cycle_draw", "draw_cards"]


def test_cycling_draw_uses_draw_replacement_effects() -> None:
    state, cid = _state_with_cycler()
    replacement_id = "cycle-draw-replacement"
    state.cards[replacement_id] = CardInstance(
        id=replacement_id,
        name="Cycle Ward",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="If you would draw a card, gain 1 life instead.",
    )
    state.players[1].battlefield.append(replacement_id)
    before_life = state.players[1].life
    before_hand = len(state.players[1].hand)
    engine = RulesEngine()

    engine.take_action(state, 1, {"type": "cycle_card", "card_id": cid})
    from rules_engine.stack_engine import resolve_top_of_stack

    resolve_top_of_stack(state)

    assert state.players[1].life == before_life + 1
    assert len(state.players[1].hand) == before_hand - 1
    assert any("replacement effect applied: draw_cards -> gain_life" in line.lower() for line in state.log)


def test_cycling_discard_cost_emits_discard_trigger_before_cycle_draw() -> None:
    state, cid = _state_with_cycler()
    payoff_id = "cycle-discard-payoff"
    state.cards[payoff_id] = CardInstance(
        id=payoff_id,
        name="Discard Payoff",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Whenever you discard a card, draw a card.",
    )
    state.players[1].battlefield.append(payoff_id)
    engine = RulesEngine()

    engine.take_action(state, 1, {"type": "cycle_card", "card_id": cid})

    assert [item.effect_key for item in state.stack] == ["cycle_draw", "draw_cards"]
    assert any("discard" in line.lower() for line in state.log)


def test_optional_cycling_trigger_can_be_declined() -> None:
    state, cid = _state_with_cycler()
    payoff_id = "optional-cycle-payoff"
    state.cards[payoff_id] = CardInstance(
        id=payoff_id,
        name="Optional Cycle Payoff",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Whenever you cycle a card, you may gain 1 life.",
    )
    state.players[1].battlefield.append(payoff_id)
    before_life = state.players[1].life
    engine = RulesEngine()

    engine.take_action(state, 1, {"type": "cycle_card", "card_id": cid})
    optional = next(item for item in state.stack if item.effect_key == "gain_life")
    optional.payload["__may_choose"] = False
    from rules_engine.stack_engine import resolve_top_of_stack

    resolve_top_of_stack(state)

    assert state.players[1].life == before_life
    assert any("declines optional effect" in line.lower() for line in state.log)


def test_variable_cycling_exposes_only_mana_payable_x_values() -> None:
    state, cid = _state_with_cycler()
    state.cards[cid].oracle_text = "Cycling {X}{1}"
    p1 = state.players[1]
    for _ in range(2):
        land_id = p1.library.pop()
        p1.battlefield.append(land_id)
        state.cards[land_id].zone = Zone.BATTLEFIELD
        state.cards[land_id].types = ["Land"]
        state.cards[land_id].name = "Island"
    moves = [m for m in RulesEngine().legal_moves(state, 1) if m.get("type") == "cycle_card"]
    assert [m.get("x_value") for m in moves] == [0, 1, 2]


def test_alternate_cycling_variant_is_detected() -> None:
    assert cycling_variant("Landcycling {2}") == "land"
    assert cycling_variant("Basic landcycling {1}") == "basic_land"
    assert cycling_variant("Wizardcycling {X}") == "wizard"


def test_x_basic_landcycling_searches_for_a_basic_land() -> None:
    state, cid = _state_with_cycler()
    state.cards[cid].name = "Ash Barrens"
    state.cards[cid].oracle_text = "Basic landcycling {X}"
    p1 = state.players[1]
    land_id = p1.library[-1]
    state.cards[land_id].types = ["Land"]
    state.cards[land_id].type_line = "Basic Land — Island"
    first_land = p1.library[-2]
    state.cards[first_land].types = ["Land"]
    state.cards[first_land].type_line = "Land — Island"
    moves = [m for m in RulesEngine().legal_moves(state, 1) if m.get("type") == "cycle_card"]
    assert [m.get("x_value") for m in moves] == [0, 1]

    engine = RulesEngine()
    engine.take_action(state, 1, {"type": "cycle_card", "card_id": cid, "x_value": 1})
    from rules_engine.stack_engine import resolve_top_of_stack

    resolve_top_of_stack(state)
    assert land_id in p1.hand
    assert land_id not in p1.library


def test_variable_cycle_x_value_reaches_dynamic_cycle_trigger() -> None:
    state, cid = _state_with_cycler()
    state.cards[cid].name = "Variable Cycler"
    state.cards[cid].oracle_text = "Cycling {X}{1}"
    p1 = state.players[1]
    for _ in range(2):
        land_id = p1.library.pop()
        p1.battlefield.append(land_id)
        state.cards[land_id].zone = Zone.BATTLEFIELD
        state.cards[land_id].types = ["Land"]
        state.cards[land_id].name = "Island"
    payoff_id = "cycle-payoff"
    p1.battlefield.append(payoff_id)
    state.cards[payoff_id] = CardInstance(
        id=payoff_id,
        name="Cycle Payoff",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="When you cycle Variable Cycler, create an X/X blue Shark creature token with flying.",
    )
    engine = RulesEngine()
    engine.take_action(state, 1, {"type": "cycle_card", "card_id": cid, "x_value": 2})
    assert state.stack[-1].effect_key == "create_shark_token"
    from rules_engine.stack_engine import resolve_top_of_stack

    resolve_top_of_stack(state)
    token = state.cards[p1.battlefield[-1]]
    assert token.name == "Shark"
    assert token.power == 2 and token.toughness == 2


def test_master_lookahead_resolves_unanswered_cycle_stack() -> None:
    state, cid = _state_with_cycler()
    from ai.agent import AIAgent

    engine = RulesEngine()
    engine.take_action(state, 1, {"type": "cycle_card", "card_id": cid})
    AIAgent(difficulty="master")._approximate_resolution_for_activated_action(
        state, {"type": "cycle_card", "card_id": cid}, 1
    )
    assert not state.stack
