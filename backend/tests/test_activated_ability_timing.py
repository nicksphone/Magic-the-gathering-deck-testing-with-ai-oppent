import pytest

from game_state.state import CardInstance, MatchFactory, StackItem, Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.state_based_actions import apply_state_based_actions


def _state(oracle_text: str):
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=7)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    source_id = state.players[1].library.pop()
    source = state.cards[source_id]
    source.zone = Zone.BATTLEFIELD
    source.types = ["Artifact"]
    source.oracle_text = oracle_text
    state.players[1].battlefield.append(source_id)
    return state, source_id


@pytest.mark.parametrize("active,step,stacked", [
    (1, Step.UPKEEP, False),
    (2, Step.PRECOMBAT_MAIN, False),
    (1, Step.POSTCOMBAT_MAIN, True),
])
def test_sorcery_only_activation_is_unavailable_and_direct_action_is_rejected(active, step, stacked) -> None:
    state, source_id = _state("{T}: Draw a card. Activate only as a sorcery.")
    state.active_player = active
    state.step = step
    if stacked:
        state.stack.append(StackItem("pending", source_id, 1, "Pending", "noop", {}))
    before_stack = list(state.stack)
    assert not any(move["type"] == "activate_ability" for move in RulesEngine().legal_moves(state, 1))
    with pytest.raises(ActionRejected, match="sorcery speed"):
        RulesEngine().take_action(
            state, 1, {"type": "activate_ability", "card_id": source_id, "ability_index": 0},
            reject_invalid=True,
        )
    assert state.stack == before_stack
    assert not state.cards[source_id].tapped


def test_sorcery_only_activation_is_available_in_own_empty_main_phase() -> None:
    state, source_id = _state("{T}: Draw a card. Activate only as a sorcery.")
    move = next(move for move in RulesEngine().legal_moves(state, 1) if move["type"] == "activate_ability")
    RulesEngine().take_action(state, 1, move, reject_invalid=True)
    assert state.cards[source_id].tapped
    assert state.stack[-1].effect_key == "draw_cards"


def test_unrestricted_activated_ability_remains_available_with_stack() -> None:
    state, source_id = _state("{T}: Draw a card.")
    state.stack.append(StackItem("pending", source_id, 1, "Pending", "noop", {}))
    assert any(move["type"] == "activate_ability" for move in RulesEngine().legal_moves(state, 1))


def _crypt_rats():
    state, source_id = _state("{X}: Crypt Rats deals X damage to each creature and each player. Spend only black mana on X.")
    source = state.cards[source_id]
    source.name = "Crypt Rats"
    source.types = ["Creature"]
    source.mana_cost = "{2}{B}"
    source.colors = ["B"]
    source.power = source.toughness = 1
    source.summoning_sick = False
    return state, source_id


def test_restricted_x_payment_uses_only_black_mana_for_x() -> None:
    state, source_id = _crypt_rats()
    state.players[1].mana_pool.update({"B": 1, "R": 3})
    before = serialize_match_snapshot(state)
    assert any(move["type"] == "activate_ability" for move in RulesEngine().legal_moves(state, 1))
    with pytest.raises(ActionRejected, match="Cannot pay activation costs"):
        checked_action(state, RulesEngine(), 1, {
            "type": "activate_ability", "card_id": source_id,
            "ability_index": 0, "targets": {"x_value": 2},
        })
    assert serialize_match_snapshot(state) == before
    with pytest.raises(ActionRejected, match="Cannot pay activation costs"):
        RulesEngine().take_action(state, 1, {
            "type": "activate_ability", "card_id": source_id,
            "ability_index": 0, "targets": {"x_value": 2},
        }, reject_invalid=True)
    assert serialize_match_snapshot(state) == before
    state.players[1].mana_pool["B"] = 2
    RulesEngine().take_action(state, 1, {
        "type": "activate_ability", "card_id": source_id,
        "ability_index": 0, "targets": {"x_value": 2},
    }, reject_invalid=True)
    assert state.players[1].mana_pool["B"] == 0
    assert state.players[1].mana_pool["R"] == 3
    assert state.stack[-1].effect_key == "damage_each_creature_and_player"


def test_crypt_rats_damage_is_simultaneous_and_both_players_can_lose() -> None:
    state, source_id = _crypt_rats()
    bear = CardInstance(
        id="bear", name="Grizzly Bears", owner=2, controller=2,
        zone=Zone.BATTLEFIELD, types=["Creature"], power=2, toughness=2,
        mana_cost="{1}{G}", type_line="Creature - Bear",
    )
    state.cards[bear.id] = bear
    state.players[2].battlefield.append(bear.id)
    state.players[1].life = state.players[2].life = 2
    state.players[1].mana_pool["B"] = 2
    RulesEngine().take_action(state, 1, {
        "type": "activate_ability", "card_id": source_id,
        "ability_index": 0, "targets": {"x_value": 2},
    }, reject_invalid=True)
    assert resolve_top_of_stack(state)
    assert state.cards[source_id].zone == state.cards[bear.id].zone == Zone.BATTLEFIELD
    apply_state_based_actions(state)
    assert state.winner == 0
    assert state.cards[source_id].zone == state.cards[bear.id].zone == Zone.GRAVEYARD
    assert state.players[1].life == state.players[2].life == 0


def test_crypt_rats_damage_respects_protection_from_black() -> None:
    state, source_id = _crypt_rats()
    bear = CardInstance(
        id="bear", name="Grizzly Bears", owner=2, controller=2,
        zone=Zone.BATTLEFIELD, types=["Creature"], power=2, toughness=2,
        mana_cost="{1}{G}", keywords=["protection from black"],
    )
    state.cards[bear.id] = bear
    state.players[2].battlefield.append(bear.id)
    state.players[1].mana_pool["B"] = 2
    RulesEngine().take_action(state, 1, {
        "type": "activate_ability", "card_id": source_id,
        "ability_index": 0, "targets": {"x_value": 2},
    }, reject_invalid=True)
    assert resolve_top_of_stack(state)
    apply_state_based_actions(state)
    assert state.cards[bear.id].zone == Zone.BATTLEFIELD
    assert state.cards[bear.id].counters.get("__damage_marked", 0) == 0
    assert state.cards[source_id].zone == Zone.GRAVEYARD


def test_ai_avoids_bad_crypt_rats_activation_but_uses_lethal_or_favorable_sweep() -> None:
    from ai.agent import AIAgent

    for own_life, opponent_life, opposing_creatures, expected in (
        (1, 20, 0, "pass_priority"),
        (20, 20, 0, "pass_priority"),
        (20, 2, 0, "activate_ability"),
        (20, 20, 2, "activate_ability"),
    ):
        state, _ = _crypt_rats()
        state.players[1].life = own_life
        state.players[2].life = opponent_life
        state.players[1].hand.clear()
        state.players[1].mana_pool.update({"B": 2, "R": 8})
        for index in range(opposing_creatures):
            bear = CardInstance(
                id=f"bear-{index}", name="Grizzly Bears", owner=2, controller=2,
                zone=Zone.BATTLEFIELD, types=["Creature"], power=2, toughness=2,
                mana_cost="{1}{G}", type_line="Creature - Bear",
            )
            state.cards[bear.id] = bear
            state.players[2].battlefield.append(bear.id)
        agent = AIAgent(difficulty="master")
        action = agent.choose_action(state, RulesEngine().legal_moves(state, 1), 1).action
        assert action["type"] == expected
        if expected == "activate_ability":
            assert action["targets"]["x_value"] == 2


def test_crypt_rats_batch_resumes_human_damage_replacements_before_lethal_sba() -> None:
    state, source_id = _crypt_rats()
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    for index in (1, 2):
        ward = CardInstance(
            id=f"hekma-{index}", name="Protection of the Hekma", owner=1, controller=1,
            zone=Zone.BATTLEFIELD, types=["Enchantment"],
            oracle_text="If a source would deal damage to you, prevent 1 of that damage.",
        )
        state.cards[ward.id] = ward
        state.players[1].battlefield.append(ward.id)
    state.players[1].mana_pool["B"] = 3
    RulesEngine().take_action(state, 1, {
        "type": "activate_ability", "card_id": source_id,
        "ability_index": 0, "targets": {"x_value": 3},
    }, reject_invalid=True)
    assert not resolve_top_of_stack(state)
    assert state.pending_replacement_choice["resume_kind"] == "damage_batch"
    assert state.cards[source_id].zone == Zone.BATTLEFIELD
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    for _ in range(2):
        move = next(move for move in RulesEngine().legal_moves(state, 1) if move["type"] == "choose_replacement")
        RulesEngine().take_action(state, 1, move, reject_invalid=True)
    assert state.pending_replacement_choice is None
    assert state.players[1].life == 19
    assert state.players[2].life == 17
    assert state.cards[source_id].zone == Zone.GRAVEYARD


def test_crypt_rats_http_rejects_wrong_color_then_accepts_announced_x() -> None:
    from fastapi.testclient import TestClient
    from main import ACTIVE_MATCHES, MatchController, app

    state, source_id = _crypt_rats()
    state.players[1].mana_pool.update({"B": 1, "R": 3})
    deck = [{"quantity": 60, "card_name": "Island"}]
    match = MatchController(
        state=state, rules=RulesEngine(), controllers={1: "human", 2: "human"}, ai={},
        mode="human_vs_human", deck_ids=(None, None), mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3,
    )
    action = {"type": "activate_ability", "card_id": source_id, "ability_index": 0, "targets": {"x_value": 2}}
    with TestClient(app) as client:
        ACTIVE_MATCHES[state.id] = match
        try:
            before = serialize_match_snapshot(match.state)
            rejected = client.post(f"/matches/{state.id}/action", json={"player_id": 1, "action": action})
            assert rejected.status_code == 422
            assert serialize_match_snapshot(match.state) == before
            match.state.players[1].mana_pool["B"] = 2
            accepted = client.post(f"/matches/{state.id}/action", json={"player_id": 1, "action": action})
            assert accepted.status_code == 200
            assert match.state.players[1].mana_pool["B"] == 0
            assert match.state.players[1].mana_pool["R"] == 3
            assert match.state.stack[-1].effect_key == "damage_each_creature_and_player"
        finally:
            ACTIVE_MATCHES.pop(state.id, None)
