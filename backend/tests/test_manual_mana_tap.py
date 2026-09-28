from __future__ import annotations

from game_state.state import MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine.action_validation import ActionRejected, checked_action
from game_state.serializers import serialize_card_view, serialize_match_snapshot
from card_data.token_definitions import named_artifact_token
from rules_engine.mana import auto_pay_cost, can_pay_with_pool_and_lands, nonland_mana_outputs
import pytest


def test_tap_lands_bulk_adds_mana_and_taps_requested_count() -> None:
    deck = [{"quantity": 60, "card_name": "Mountain"}]
    state = MatchFactory.from_decks(deck, deck)
    engine = RulesEngine()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.priority_player = 1
    p1 = state.players[1]

    # Stage exactly three Mountains as untapped battlefield lands.
    p1.battlefield = []
    for _ in range(3):
        cid = p1.library.pop()
        p1.battlefield.append(cid)
        card = state.cards[cid]
        card.zone = Zone.BATTLEFIELD
        card.name = "Mountain"
        card.types = ["Land"]
        card.tapped = False

    engine.take_action(state, 1, {"type": "tap_lands_bulk", "land_name": "Mountain", "count": 2})

    tapped = sum(1 for cid in p1.battlefield if state.cards[cid].tapped)
    assert tapped == 2
    assert p1.mana_pool["R"] == 2


def _mana_game():
    deck = [{"quantity": 60, "card_name": "Forest", "type_line": "Basic Land - Forest", "oracle_text": "{T}: Add {G}."}]
    state = MatchFactory.from_decks(deck, deck, seed=8)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    return state


def test_manual_treasure_mana_sacrifices_token_and_persists_pool() -> None:
    state = _mana_game()
    cid = state.players[1].library.pop()
    token = state.cards[cid]
    token.name = "Treasure"
    token.types = ["Artifact", "Token"]
    token.type_line = "Token Artifact - Treasure"
    token.oracle_text = named_artifact_token("Treasure")["oracle_text"]
    token.is_token = True
    token.zone = Zone.BATTLEFIELD
    state.players[1].battlefield.append(cid)
    assert serialize_card_view(state, cid)["mana_source_colors"] == list("BGRUW")
    result = checked_action(state, RulesEngine(), 1, {"type": "tap_nonland_for_mana", "card_id": cid, "color": "U"})
    assert result.players[1].mana_pool["U"] == 1
    assert cid not in result.players[1].battlefield
    assert result.cards[cid].zone == Zone.CEASED
    assert state.players[1].mana_pool["U"] == 0
    assert cid in state.players[1].battlefield


def test_manual_creature_mana_requires_ready_source_and_valid_color() -> None:
    state = _mana_game()
    cid = state.players[1].library.pop()
    creature = state.cards[cid]
    creature.name = "Mana Creature"
    creature.types = ["Creature"]
    creature.oracle_text = "{T}: Add {G}."
    creature.zone = Zone.BATTLEFIELD
    creature.summoning_sick = True
    state.players[1].battlefield.append(cid)
    action = {"type": "tap_nonland_for_mana", "card_id": cid, "color": "G"}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, action)
    assert serialize_match_snapshot(state) == before
    creature.summoning_sick = False
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {**action, "color": "U"})
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 2, action)
    result = checked_action(state, RulesEngine(), 1, action)
    assert result.players[1].mana_pool["G"] == 1
    assert result.cards[cid].tapped


@pytest.mark.parametrize("name,types,text,color,amount", [
    ("Llanowar Tribe", ["Creature"], "{T}: Add {G}{G}{G}.", "G", 3),
    ("Sol Ring", ["Artifact"], "{T}: Add {C}{C}.", "C", 2),
])
def test_fixed_multi_mana_sources_produce_printed_amount(name, types, text, color, amount) -> None:
    state = _mana_game()
    cid = state.players[1].library.pop()
    source = state.cards[cid]
    source.name = name
    source.types = types
    source.oracle_text = text
    source.zone = Zone.BATTLEFIELD
    source.summoning_sick = False
    state.players[1].battlefield.append(cid)
    assert nonland_mana_outputs(state, cid, source) == {color: amount}
    assert serialize_card_view(state, cid)["mana_source_amounts"] == {color: amount}
    assert can_pay_with_pool_and_lands(state, 1, "".join("{" + color + "}" for _ in range(amount)))
    manual = checked_action(state, RulesEngine(), 1, {"type": "tap_nonland_for_mana", "card_id": cid, "color": color})
    assert manual.players[1].mana_pool[color] == amount
    assert manual.cards[cid].tapped
    cost = "".join("{" + color + "}" for _ in range(amount - 1))
    assert auto_pay_cost(state, 1, cost)
    assert state.cards[cid].tapped
    assert state.players[1].mana_pool[color] == 1


def test_one_flexible_source_cannot_pay_two_distinct_colored_pips() -> None:
    state = _mana_game()
    cid = state.players[1].library.pop()
    source = state.cards[cid]
    source.name = "Treasure"
    source.types = ["Artifact", "Token"]
    source.oracle_text = named_artifact_token("Treasure")["oracle_text"]
    source.zone = Zone.BATTLEFIELD
    source.is_token = True
    state.players[1].battlefield.append(cid)
    assert not can_pay_with_pool_and_lands(state, 1, "{R}{G}")
    before = serialize_match_snapshot(state)
    assert not auto_pay_cost(state, 1, "{R}{G}")
    assert serialize_match_snapshot(state) == before
    assert can_pay_with_pool_and_lands(state, 1, "{R}")


def test_basic_is_used_before_dual_to_preserve_other_color() -> None:
    state = _mana_game()
    dual_id = state.players[1].library.pop()
    basic_id = state.players[1].library.pop()
    for cid in (dual_id, basic_id):
        state.cards[cid].zone = Zone.BATTLEFIELD
        state.players[1].battlefield.append(cid)
    dual = state.cards[dual_id]
    dual.name = "Watery Grave"
    dual.types = ["Land"]
    dual.type_line = "Land - Island Swamp"
    dual.oracle_text = "{T}: Add {U} or {B}."
    basic = state.cards[basic_id]
    basic.name = "Island"
    basic.types = ["Land"]
    basic.type_line = "Basic Land - Island"
    basic.oracle_text = "{T}: Add {U}."
    assert can_pay_with_pool_and_lands(state, 1, "{U}{B}")
    assert auto_pay_cost(state, 1, "{U}{B}")
    assert dual.tapped and basic.tapped
