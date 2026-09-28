from card_data.fallback_cards import fallback_card_payload
from card_data.token_definitions import named_artifact_token
from game_state.state import MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine.mana import auto_pay_cost, can_pay_with_pool_and_lands
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.state_based_actions import apply_state_based_actions


def test_offline_named_artifact_token_definitions_match_printed_oracle() -> None:
    for name in ("Food", "Blood", "Treasure"):
        token = named_artifact_token(name)
        assert token["name"] == name
        assert token["type_line"] == f"Token Artifact — {name}"
        assert token["scryfall_id"]
    assert named_artifact_token("Invented Token") is None
    assert named_artifact_token("Treasure")["oracle_text"] == "{T}, Sacrifice this token: Add one mana of any color."


def test_fable_chapter_goblin_attack_creates_real_treasure_for_colored_mana() -> None:
    deck = [{"quantity": 60, "card_name": "Forest", "type_line": "Basic Land - Forest", "oracle_text": "{T}: Add {G}."}]
    state = MatchFactory.from_decks(deck, deck, seed=89)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    fable_id = state.players[1].library.pop()
    fable = state.cards[fable_id]
    front = fallback_card_payload("Fable of the Mirror-Breaker")["card_faces"][0]
    fable.name = front["name"]
    fable.oracle_text = front["oracle_text"]
    fable.type_line = front["type_line"]
    fable.types = ["Enchantment", "Saga"]
    fable.zone = Zone.BATTLEFIELD
    state.players[1].battlefield.append(fable_id)

    rules = RulesEngine()
    rules._advance_sagas(state)
    assert state.stack[-1].label.endswith("chapter 1")
    resolve_top_of_stack(state)
    goblin_id = next(cid for cid in state.players[1].battlefield if state.cards[cid].is_token and state.cards[cid].name == "Goblin Shaman")
    goblin = state.cards[goblin_id]
    assert goblin.oracle_text == "Whenever this token attacks, create a Treasure token."

    goblin.summoning_sick = False
    state.step = Step.DECLARE_ATTACKERS
    state.priority_player = 1
    rules.take_action(state, 1, {"type": "attack", "attackers": [goblin_id]}, reject_invalid=True)
    assert any(item.effect_key == "create_token" and item.payload.get("name") == "Treasure" for item in state.stack)
    resolve_top_of_stack(state)
    treasure_id = next(cid for cid in state.players[1].battlefield if state.cards[cid].name == "Treasure")
    treasure = state.cards[treasure_id]
    assert treasure.oracle_text == named_artifact_token("Treasure")["oracle_text"]
    assert treasure.types == ["Artifact", "Token"]
    assert can_pay_with_pool_and_lands(state, 1, "{R}")
    assert not can_pay_with_pool_and_lands(state, 1, "{C}")
    assert auto_pay_cost(state, 1, "{R}")
    assert treasure_id not in state.players[1].battlefield
    apply_state_based_actions(state)
    assert treasure.zone == Zone.CEASED
