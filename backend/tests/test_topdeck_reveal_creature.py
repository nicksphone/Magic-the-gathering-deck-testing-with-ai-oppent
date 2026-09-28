"""Canonical creature-reveal abilities choose at resolution, not on activation."""

from fastapi.testclient import TestClient

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import infer_effect_from_oracle
from effects.registry import resolve_effect
from ai.agent import AIAgent
from rules_engine.stack_engine import resolve_top_of_stack
from main import ACTIVE_MATCHES, MatchController, app


RECRUITMENT_TEXT = (
    "{3}{W}: Look at the top four cards of your library. You may reveal a creature card "
    "with mana value 3 or less from among them and put it into your hand. "
    "Put the rest on the bottom of your library in a random order."
)
MILITIA_TEXT = (
    "Vigilance (Attacking doesn't cause this creature to tap.)\n"
    "When this creature enters, look at the top four cards of your library. You may reveal "
    "a creature card with power 2 or less from among them and put it into your hand. "
    "Put the rest on the bottom of your library in a random order."
)


def setup(oracle_text: str):
    deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=17)
    state.pregame_pending = False
    player = state.players[1]
    source = state.cards[player.hand[0]]
    source.name = "Recruitment Officer" if oracle_text == RECRUITMENT_TEXT else "Militia Bugler"
    source.oracle_text = oracle_text
    top = player.library[-4:]
    for cid, name, cost, power, types in zip(top,
        ["Adeline, Resplendent Cathar", "Topiary Stomper", "Sheoldred, the Apocalypse", "Island"],
        ["{1}{W}{W}", "{1}{G}{G}", "{2}{B}{B}", ""],
        [1, 4, 4, None],
        [["Creature"], ["Creature"], ["Creature"], ["Land"]],
    ):
        card = state.cards[cid]
        card.name, card.mana_cost, card.power, card.types = name, cost, power, types
    return state, source, top


def test_recruitment_officer_uses_mana_value_and_reveals_a_qualifying_creature():
    state, source, top = setup(RECRUITMENT_TEXT)
    key, payload = infer_effect_from_oracle(state, source, 1)
    assert key == "topdeck_reveal_creature_to_hand"
    assert payload["mv_max"] == 3 and "power_max" not in payload
    assert payload["bottom_random"] is True
    resolve_effect(state, 1, key, payload)
    assert top[1] in state.players[1].hand  # MV 3, despite power 4.
    assert top[2] not in state.players[1].hand  # MV 4 is not eligible.


def test_ai_creature_reveal_chooses_at_resolution() -> None:
    state, source, top = setup(RECRUITMENT_TEXT)
    state.mechanic_choice_players = {1}
    key, payload = infer_effect_from_oracle(state, source, 1)
    resolve_effect(state, 1, key, payload)
    assert state.pending_mechanic_choice["kind"] == "topdeck_reveal_creature"
    action = AIAgent(archetype="Midrange").choose_action(state, RulesEngine().legal_moves(state, 1), 1).action
    assert action == {"type": "choose_mechanic", "card_ids": [top[1]]}
    RulesEngine().take_action(state, 1, action, reject_invalid=True)
    assert top[1] in state.players[1].hand
    assert state.pending_mechanic_choice is None
    assert set(state.players[1].library[:3]) == set(top) - {top[1]}
    assert not any("not inferred" in line for line in state.log)


def test_power_threshold_remains_distinct_and_human_may_decline_after_restart():
    state, source, top = setup(MILITIA_TEXT)
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    key, payload = infer_effect_from_oracle(state, source, 1)
    assert key == "topdeck_reveal_creature_to_hand"
    assert payload["power_max"] == 2 and "mv_max" not in payload
    resolve_effect(state, 1, key, payload)
    pending = state.pending_mechanic_choice
    assert pending and pending["kind"] == "topdeck_reveal_creature"
    assert top[0] in pending["options"] and top[1] not in pending["options"]
    assert "__none__" in pending["options"]
    assert state.players[1].library[-4:] == top  # No premature reveal or zone movement.

    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    moves = RulesEngine().legal_moves(restored, 1)
    assert moves[0]["type"] == "choose_mechanic"
    assert moves[0]["option_labels"]["__none__"] == "Reveal none"
    RulesEngine().take_action(restored, 1, {"type": "choose_mechanic", "card_ids": ["__none__"]}, reject_invalid=True)
    assert restored.pending_mechanic_choice is None
    assert top[0] not in restored.players[1].hand
    assert set(restored.players[1].library[:4]) == set(top)


def test_human_recruitment_officer_choice_resumes_activated_stack_after_snapshot():
    state, source, _ = setup(RECRUITMENT_TEXT)
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    state.kept_hands = {1, 2}
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    player = state.players[1]
    player.hand.remove(source.id)
    player.battlefield.append(source.id)
    source.zone = Zone.BATTLEFIELD
    source.types = ["Creature"]
    source.type_line = "Creature - Human Soldier"
    source.mana_cost = "{W}"
    for _ in range(4):
        cid = player.library.pop(0)
        land = state.cards[cid]
        land.name = "Plains"
        land.type_line = "Basic Land - Plains"
        land.types = ["Land"]
        land.zone = Zone.BATTLEFIELD
        player.battlefield.append(cid)
    top = player.library[-4:]
    choice = top[0]
    state.cards[choice].types = ["Creature"]
    state.cards[choice].name = "Adeline, Resplendent Cathar"
    state.cards[choice].mana_cost = "{1}{W}{W}"
    engine = RulesEngine()
    ability = next(move for move in engine.legal_moves(state, 1) if move["type"] == "activate_ability" and move["card_id"] == source.id)
    engine.take_action(state, 1, ability)
    assert state.stack and state.stack[-1].effect_key == "topdeck_reveal_creature_to_hand"
    resolve_top_of_stack(state)
    assert state.pending_mechanic_choice and state.pending_mechanic_choice["resolving_item"]
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    engine.take_action(restored, 1, {"type": "choose_mechanic", "card_ids": [choice]}, reject_invalid=True)
    assert choice in restored.players[1].hand
    assert restored.pending_mechanic_choice is None
    assert not restored.stack
    assert any("Recruitment Officer ability resolves" in line for line in restored.log)


def test_http_human_topdeck_choice_exposes_options_and_accepts_selection():
    state, source, top = setup(MILITIA_TEXT)
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    key, payload = infer_effect_from_oracle(state, source, 1)
    resolve_effect(state, 1, key, payload)
    deck = [{"quantity": 60, "card_name": "Island"}]
    match = MatchController(
        state=state, rules=RulesEngine(), controllers={1: "human", 2: "ai"}, ai={},
        mode="player_vs_ai", deck_ids=(None, None), mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3,
    )
    with TestClient(app) as client:
        ACTIVE_MATCHES[state.id] = match
        try:
            public = client.get(f"/matches/{state.id}")
            assert public.status_code == 200
            assert public.json()["pending_mechanic_choice"]["kind"] == "topdeck_reveal_creature"
            legal = client.get(f"/matches/{state.id}/legal-moves")
            assert legal.status_code == 200
            assert legal.json()["moves"][0]["option_labels"]["__none__"] == "Reveal none"
            chosen = client.post(f"/matches/{state.id}/action", json={
                "player_id": 1, "action": {"type": "choose_mechanic", "card_ids": [top[0]]},
            })
            assert chosen.status_code == 200
            assert chosen.json()["pending_mechanic_choice"] is None
            assert any(card["id"] == top[0] for card in chosen.json()["players"]["1"]["hand"])
        finally:
            ACTIVE_MATCHES.pop(state.id, None)
