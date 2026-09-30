"""Canonical conditional entry, mandatory instruction and state-aware mana."""
import pytest

from ai.agent import AIAgent
from game_state.serializers import deserialize_match_snapshot, serialize_card_view, serialize_match_snapshot
from game_state.state import Zone, Step, pregame_actor
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.mana import land_mana_colors, can_pay_with_pool_and_lands, auto_pay_cost
from rules_engine.opening_hand import can_begin_on_battlefield
from tests.test_opening_hand import opening_game, add_opening, keep_both
from tests.test_api_input_contracts import game, persist, snapshot


def enter_conditional(starter=1):
    state, rules = opening_game(starter), RulesEngine()
    owner = 3 - starter
    cid = add_opening(state, "Gemstone Caverns", owner)
    state = keep_both(state)
    state = checked_action(state, rules, owner, {"type": "choose_mechanic", "card_ids": [cid]})
    return state, cid, owner


@pytest.mark.parametrize("starter", [1, 2])
def test_nonstarter_entry_counter_then_mandatory_exile_survives_snapshot(starter):
    state, cid, owner = enter_conditional(starter)
    rules = RulesEngine()
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    assert state.cards[cid].counters["luck"] == 1
    assert state.pregame_pending and state.pending_mechanic_choice["kind"] == "opening_hand_exile"
    assert pregame_actor(state) == owner
    assert cid not in state.pending_mechanic_choice["options"]
    assert not state.stack and not state.players[owner].lands_played_this_turn
    before = serialize_match_snapshot(state)
    for pid, ids in ((starter, [state.players[owner].hand[0]]), (owner, [cid]), (owner, [])):
        with pytest.raises(ActionRejected):
            checked_action(state, rules, pid, {"type": "choose_mechanic", "card_ids": ids})
        assert serialize_match_snapshot(state) == before
    restored = deserialize_match_snapshot(before)
    exiled = state.players[owner].hand[0]
    for candidate in (state, restored):
        result = checked_action(candidate, rules, owner, {"type": "choose_mechanic", "card_ids": [exiled]})
        assert not result.pregame_pending
        assert result.cards[exiled].zone == Zone.EXILE
        assert exiled not in result.players[owner].graveyard
        assert land_mana_colors(result.cards[cid]) == set("WUBRG")


def test_starter_cannot_use_conditional_permission_and_may_decline():
    state = opening_game()
    cid = add_opening(state, "Gemstone Caverns", 1)
    assert not can_begin_on_battlefield(state.cards[cid], state)
    assert not can_begin_on_battlefield(state.cards[cid], state, 99)
    state = keep_both(state)
    assert state.pending_mechanic_choice["options"] == ["__finish_opening__"]
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": [cid]})
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": ["__finish_opening__"]})
    assert cid in state.players[1].hand and not state.cards[cid].counters


def test_empty_followup_hand_does_not_turn_exile_instruction_into_cost():
    state = opening_game()
    cid = add_opening(state, "Gemstone Caverns", 2)
    # Construct the one-card opening boundary without orphaning the other cards.
    for other in list(state.players[2].hand):
        if other != cid:
            state.players[2].hand.remove(other)
            state.players[2].library.append(other)
            state.cards[other].move_to_zone(Zone.LIBRARY)
    state = keep_both(state)
    state = checked_action(state, RulesEngine(), 2, {"type": "choose_mechanic", "card_ids": [cid]})
    assert not state.pregame_pending and not state.players[2].hand
    assert state.cards[cid].counters["luck"] == 1


def test_normal_land_play_has_no_counter_and_all_payment_paths_obey_current_counter():
    state = opening_game()
    cid = add_opening(state, "Gemstone Caverns", 1)
    state.pregame_pending = False
    state.step = Step.PRECOMBAT_MAIN
    state = checked_action(state, RulesEngine(), 1, {"type": "play_land", "card_id": cid})
    assert land_mana_colors(state.cards[cid]) == {"C"}
    assert not can_pay_with_pool_and_lands(state, 1, "{U}")
    assert can_pay_with_pool_and_lands(state, 1, "{C}")
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {"type": "tap_land_for_mana", "card_id": cid, "color": "U"})
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        RulesEngine().take_action(state, 1, {"type": "tap_land_for_mana", "card_id": cid, "color": "U"}, reject_invalid=True)
    assert serialize_match_snapshot(state) == before
    state.cards[cid].counters["luck"] = 1
    assert serialize_card_view(state, cid)["mana_source_colors"] == sorted("WUBRG")
    assert can_pay_with_pool_and_lands(state, 1, "{U}")
    assert not can_pay_with_pool_and_lands(state, 1, "{C}")
    assert auto_pay_cost(state, 1, "{U}") and state.cards[cid].tapped
    state.cards[cid].tapped = False
    state.cards[cid].counters.pop("luck")
    assert serialize_card_view(state, cid)["mana_source_colors"] == ["C"]
    assert not auto_pay_cost(state, 1, "{R}")


def test_bulk_tap_filters_same_name_by_actual_output_before_counting():
    state = opening_game()
    plain = add_opening(state, "Gemstone Caverns", 1)
    colored = add_opening(state, "Gemstone Caverns", 1)
    for cid in (plain, colored):
        state.players[1].hand.remove(cid)
        state.players[1].battlefield.append(cid)
        state.cards[cid].move_to_zone(Zone.BATTLEFIELD)
    state.cards[colored].counters["luck"] = 1
    state.pregame_pending = False
    state.step = Step.PRECOMBAT_MAIN
    action = {"type": "tap_lands_bulk", "land_name": "Gemstone Caverns", "count": 2, "color": "U"}
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, action)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        RulesEngine().take_action(state, 1, action, reject_invalid=True)
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, RulesEngine(), 1, {**action, "count": 1})
    assert state.cards[colored].tapped and not state.cards[plain].tapped
    assert state.players[1].mana_pool["U"] == 1


@pytest.mark.parametrize("style", ["Aggro", "Control", "Ramp", "Tempo", "Tokens"])
def test_ai_completes_exile_instruction_with_a_legal_remaining_card(style):
    state, cid, owner = enter_conditional()
    moves = RulesEngine().legal_moves(state, owner)
    decision = AIAgent(difficulty="master", archetype=style).choose_action(state, moves, owner)
    assert decision.action["card_ids"][0] in state.players[owner].hand
    result = checked_action(state, RulesEngine(), owner, decision.action)
    assert not result.pregame_pending and cid in result.players[owner].battlefield


def test_http_partial_entry_restores_counter_and_exile_owner(game):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository

    client, controller = game
    controller.state.pregame_pending = True
    cid = add_opening(controller.state, "Gemstone Caverns", 2)
    persist(controller)
    path = f"/matches/{controller.state.id}"
    for pid in (1, 2):
        response = client.post(path + "/action", json={"player_id": pid, "action": {"type": "keep_hand"}})
        assert response.status_code == 200, response.text
    response = client.post(path + "/action", json={"player_id": 2, "action": {"type": "choose_mechanic", "card_ids": [cid]}})
    assert response.status_code == 200, response.text
    assert response.json()["pending_mechanic_choice"]["kind"] == "opening_hand_exile"
    before = snapshot(controller)
    assert client.post(path + "/action", json={"player_id": 1, "action": {"type": "pass_priority"}}).status_code == 422
    assert snapshot(controller) == before
    main.ACTIVE_MATCHES.pop(controller.state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), controller.state.id)
    restored = main.ACTIVE_MATCHES[controller.state.id]
    assert restored.state.cards[cid].counters["luck"] == 1
    assert client.get(path + "/legal-moves").json()["player_id"] == 2
    selected = restored.state.players[2].hand[0]
    response = client.post(path + "/action", json={"player_id": 2, "action": {"type": "choose_mechanic", "card_ids": [selected]}})
    assert response.status_code == 200 and not response.json()["pregame_pending"]
    assert selected in restored.state.players[2].exile
