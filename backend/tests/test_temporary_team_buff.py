from card_data.fallback_cards import fallback_card_payload
from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.continuous import effective_power, effective_toughness, has_keyword
from rules_engine.engine import RulesEngine
from rules_engine.events import emit_event
from rules_engine.stack_engine import resolve_top_of_stack


def test_etb_team_buff_grants_haste_to_current_friendly_creatures_only() -> None:
    deck = [{"quantity": 60, "card_name": "Mountain"}]
    state = MatchFactory.from_decks(deck, deck, seed=1104)
    oracle = fallback_card_payload("Imodane's Recruiter")
    assert oracle is not None
    recruiter = CardInstance(
        "recruiter", oracle["name"], 1, 1, Zone.BATTLEFIELD, ["Creature"],
        power=2, toughness=2, oracle_text=oracle["oracle_text"],
    )
    state.cards[recruiter.id] = recruiter
    state.players[1].battlefield.append(recruiter.id)
    for card_id, controller in (("ally", 1), ("enemy", 2)):
        card = CardInstance(card_id, card_id, controller, controller, Zone.BATTLEFIELD,
                            ["Creature"], power=2, toughness=2)
        state.cards[card_id] = card
        state.players[controller].battlefield.append(card_id)

    emit_event(state, "enters_battlefield", {"card_id": recruiter.id, "controller": 1})
    assert len(state.stack) == 1
    assert state.stack[-1].effect_key == "temporary_pt_buff_all"
    assert state.stack[-1].payload["controller_only"] is True
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(state)
    for card_id in ("recruiter", "ally"):
        assert effective_power(state, card_id) == 3
        assert effective_toughness(state, card_id) == 2
        assert has_keyword(state, card_id, "haste")
    assert effective_power(state, "enemy") == 2
    assert not has_keyword(state, "enemy", "haste")

    newcomer = CardInstance("new", "new", 1, 1, Zone.BATTLEFIELD, ["Creature"], power=2, toughness=2)
    state.cards[newcomer.id] = newcomer
    state.players[1].battlefield.append(newcomer.id)
    assert effective_power(state, newcomer.id) == 2
    assert not has_keyword(state, newcomer.id, "haste")

    RulesEngine()._clear_marked_damage(state)
    assert effective_power(state, "ally") == 2
    assert not has_keyword(state, "ally", "haste")


def test_team_buff_handler_still_supports_all_creatures_debuff() -> None:
    deck = [{"quantity": 60, "card_name": "Mountain"}]
    state = MatchFactory.from_decks(deck, deck, seed=1105)
    for card_id, controller in (("ally", 1), ("enemy", 2)):
        card = CardInstance(card_id, card_id, controller, controller, Zone.BATTLEFIELD,
                            ["Creature"], power=3, toughness=3)
        state.cards[card_id] = card
        state.players[controller].battlefield.append(card_id)
    resolve_effect(state, 1, "temporary_pt_buff_all", {"power": -1, "toughness": -1})
    assert effective_toughness(state, "ally") == effective_toughness(state, "enemy") == 2
