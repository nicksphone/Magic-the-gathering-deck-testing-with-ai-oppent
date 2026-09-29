from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ai.agent import AIAgent
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from main import ACTIVE_MATCHES, MatchController, app
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack


def _state():
    deck = [{"quantity": 60, "card_name": "Swamp"}]
    state = MatchFactory.from_decks(deck, deck, seed=919)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    state.mechanic_choice_players = {1, 2}
    state.players[1].mana_pool = {"B": 1, "C": 2}
    spell_id = state.players[1].hand[0]
    card = state.cards[spell_id]
    card.name = "Coercion"
    card.mana_cost = "{2}{B}"
    card.types = ["Sorcery"]
    card.type_line = "Sorcery"
    card.oracle_text = "Target opponent reveals their hand. You choose a card from it. That player discards that card."
    return state, spell_id


def test_coercion_caster_chooses_from_opponents_revealed_hand():
    state, spell_id = _state()
    move = next(move for move in RulesEngine().legal_moves(state, 1)
                if move.get("type") == "cast_spell" and move.get("card_id") == spell_id)
    assert [target["id"] for target in move["target_hints"]["player_targets"]] == [2]
    for targets in ({}, {"target_player": 1}):
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), 1, {"type": "cast_spell", "card_id": spell_id, "targets": targets})
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": spell_id, "targets": {"target_player": 2},
    })
    assert state.stack[-1].effect_key == "choose_revealed_discard"
    assert not resolve_top_of_stack(state)
    pending = state.pending_mechanic_choice
    assert pending["player_id"] == 1 and pending["target_player"] == 2
    assert pending["options"] == state.players[2].hand
    selected = pending["options"][-1]
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 2, {"type": "choose_mechanic", "card_ids": [selected]})
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": [selected]})
    assert selected in state.players[2].graveyard
    assert selected not in state.players[2].hand
    assert state.cards[spell_id].zone == Zone.GRAVEYARD
    assert state.pending_mechanic_choice is None and not state.stack


def test_ai_chooses_one_revealed_opponent_card():
    state, spell_id = _state()
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": spell_id, "targets": {"target_player": 2},
    })
    resolve_top_of_stack(state)
    options = RulesEngine().legal_moves(state, 1)
    choice = AIAgent(difficulty="master", archetype="Control").choose_action(state, options, 1)
    assert choice.action["card_ids"][0] in state.players[2].hand
    state = checked_action(state, RulesEngine(), 1, choice.action)
    assert len(state.players[2].graveyard) == 1


def test_ai_values_revealed_cards_for_opponents_archetype():
    state, spell_id = _state()
    counter_id, bolt_id = state.players[2].hand[:2]
    counter = state.cards[counter_id]
    counter.name, counter.types, counter.type_line = "Counterspell", ["Instant"], "Instant"
    counter.mana_cost, counter.oracle_text = "{U}{U}", "Counter target spell."
    bolt = state.cards[bolt_id]
    bolt.name, bolt.types, bolt.type_line = "Lightning Bolt", ["Instant"], "Instant"
    bolt.mana_cost, bolt.oracle_text = "{R}", "Lightning Bolt deals 3 damage to any target."
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": spell_id, "targets": {"target_player": 2},
    })
    resolve_top_of_stack(state)
    ai = AIAgent(difficulty="master", archetype="Aggro", opponent_archetype="Control")
    decision = ai.choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action["card_ids"] == [counter_id]


def test_coercion_reveals_options_only_during_casters_choice():
    state, spell_id = _state()
    deck = [{"quantity": 60, "card_name": "Swamp"}]
    controller = MatchController(
        state=state, rules=RulesEngine(), controllers={1: "human", 2: "ai"}, ai={},
        mode="player_vs_ai", deck_ids=(None, None), mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3,
    )
    with TestClient(app) as client:
        ACTIVE_MATCHES[state.id] = controller
        try:
            initial = client.get(f"/matches/{state.id}").json()
            assert initial["players"]["2"]["hand"] == []
            controller.state = checked_action(state, RulesEngine(), 1, {
                "type": "cast_spell", "card_id": spell_id, "targets": {"target_player": 2},
            })
            resolve_top_of_stack(controller.state)
            public = client.get(f"/matches/{state.id}").json()
            assert public["players"]["2"]["hand"] == []
            assert any("reveals their hand: Swamp" in line for line in public["log"])
            move = client.get(f"/matches/{state.id}/legal-moves?player_id=1").json()["moves"][0]
            assert move["kind"] == "choose_revealed_discard"
            assert move["options"] == controller.state.players[2].hand
            assert all(move["option_labels"][cid] == controller.state.cards[cid].name for cid in move["options"])
            assert client.get(f"/matches/{state.id}/legal-moves?player_id=2").status_code == 403
        finally:
            ACTIVE_MATCHES.pop(state.id, None)


def _selective_state(name: str, oracle: str):
    state, spell_id = _state()
    spell = state.cards[spell_id]
    spell.name = name
    spell.mana_cost = "{B}"
    spell.oracle_text = oracle
    state.players[1].mana_pool = {"B": 1}
    hand = state.players[2].hand
    forest = state.cards[hand[0]]
    forest.name, forest.types, forest.type_line = "Forest", ["Land"], "Basic Land - Forest"
    bolt = state.cards[hand[1]]
    bolt.name, bolt.types, bolt.type_line = "Lightning Bolt", ["Instant"], "Instant"
    bolt.mana_cost = "{R}"
    bolt.oracle_text = "Lightning Bolt deals 3 damage to any target."
    elf = state.cards[hand[2]]
    elf.name, elf.types, elf.type_line = "Llanowar Elves", ["Creature"], "Creature - Elf Druid"
    elf.mana_cost, elf.power, elf.toughness = "{G}", 1, 1
    elf.oracle_text = "{T}: Add {G}."
    return state, spell_id, {"forest": hand[0], "bolt": hand[1], "elf": hand[2]}


def test_thoughtseize_filters_lands_then_loses_life_after_discard_choice():
    state, spell_id, cards = _selective_state(
        "Thoughtseize",
        "Target player reveals their hand. You choose a nonland card from it. "
        "That player discards that card. You lose 2 life.",
    )
    for targets in ({}, {"target_player": 3}):
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), 1, {
                "type": "cast_spell", "card_id": spell_id, "targets": targets,
            })
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": spell_id, "targets": {"target_player": 2},
    })
    assert state.stack[-1].effect_key == "effect_sequence"
    assert not resolve_top_of_stack(state)
    assert state.players[1].life == 20
    pending = state.pending_mechanic_choice
    assert pending["options"] == [cards["bolt"], cards["elf"]]
    assert any("reveals their hand:" in line and "Forest" in line and "Lightning Bolt" in line
               and "Llanowar Elves" in line for line in state.log)
    assert pending["continuation_effects"] == [{
        "effect_key": "lose_life", "payload": {"target_player": 1, "amount": 2, "__source_card_id": spell_id},
    }]
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": [cards["forest"]]})
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": [cards["bolt"]]})
    assert cards["bolt"] in state.players[2].graveyard
    assert cards["forest"] in state.players[2].hand
    assert state.players[1].life == 18
    assert state.cards[spell_id].zone == Zone.GRAVEYARD
    assert state.pending_mechanic_choice is None and not state.stack


def test_duress_filters_creatures_and_lands_without_life_loss():
    state, spell_id, cards = _selective_state(
        "Duress",
        "Target opponent reveals their hand. You choose a noncreature, nonland card from it. "
        "That player discards that card.",
    )
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": spell_id, "targets": {"target_player": 2},
    })
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice["options"] == [cards["bolt"]]
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": [cards["bolt"]]})
    assert state.players[1].life == 20
    assert cards["bolt"] in state.players[2].graveyard
    assert cards["elf"] in state.players[2].hand


def test_inquisition_filters_by_type_and_mana_value_across_snapshot():
    state, spell_id, cards = _selective_state(
        "Inquisition of Kozilek",
        "Target player reveals their hand. You choose a nonland card from it with mana value 3 or less. "
        "That player discards that card.",
    )
    expensive_id = state.players[2].hand[3]
    expensive = state.cards[expensive_id]
    expensive.name, expensive.types, expensive.type_line = "Serra Angel", ["Creature"], "Creature - Angel"
    expensive.mana_cost = "{3}{W}{W}"
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": spell_id, "targets": {"target_player": 2},
    })
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice["options"] == [cards["bolt"], cards["elf"]]
    assert any("Serra Angel" in line and "Forest" in line for line in state.log)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": [expensive_id]})
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": [cards["elf"]]})
    assert cards["elf"] in state.players[2].graveyard
    assert expensive_id in state.players[2].hand


def test_despise_offers_creature_or_planeswalker_only():
    state, spell_id, cards = _selective_state(
        "Despise",
        "Target opponent reveals their hand. You choose a creature or planeswalker card from it. "
        "That player discards that card.",
    )
    walker_id = state.players[2].hand[3]
    walker = state.cards[walker_id]
    walker.name, walker.types, walker.type_line = "Jace, the Mind Sculptor", ["Planeswalker"], "Legendary Planeswalker - Jace"
    walker.mana_cost = "{2}{U}{U}"
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": spell_id, "targets": {"target_player": 2},
    })
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice["options"] == [cards["elf"], walker_id]
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": [walker_id]})
    assert walker_id in state.players[2].graveyard
    assert cards["bolt"] in state.players[2].hand


def test_appetite_exiles_only_expensive_revealed_card_across_snapshot():
    from rules_engine.zone_actions import discard_selected

    state, spell_id, cards = _selective_state(
        "Appetite for Brains",
        "Target opponent reveals their hand. You choose a card from it with mana value 4 or greater and exile that card.",
    )
    expensive_id = state.players[2].hand[3]
    expensive = state.cards[expensive_id]
    expensive.name, expensive.types, expensive.type_line = "Serra Angel", ["Creature"], "Creature - Angel"
    expensive.mana_cost = "{3}{W}{W}"
    caress = CardInstance("caress", "Liliana's Caress", 1, 1, Zone.BATTLEFIELD, ["Enchantment"],
                          oracle_text="Whenever an opponent discards a card, that player loses 2 life.")
    state.cards[caress.id] = caress
    state.players[1].battlefield.append(caress.id)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {"type": "cast_spell", "card_id": spell_id, "targets": {}})
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": spell_id, "targets": {"target_player": 2},
    })
    assert state.stack[-1].effect_key == "choose_revealed_exile"
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice["kind"] == "choose_revealed_exile"
    assert state.pending_mechanic_choice["options"] == [expensive_id]
    assert any("Forest" in line and "Lightning Bolt" in line and "Serra Angel" in line for line in state.log)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": [cards["bolt"]]})
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": [expensive_id]})
    assert expensive_id in state.players[2].exile
    assert expensive_id not in state.players[2].hand
    assert state.cards[expensive_id].zone == Zone.EXILE
    assert not state.players[2].graveyard
    assert not any("discards Serra Angel" in line for line in state.log)
    assert state.cards[spell_id].zone == Zone.GRAVEYARD
    assert state.pending_mechanic_choice is None and not state.stack
    assert discard_selected(state, 2, [cards["bolt"]])
    assert any("Liliana's Caress" in item.label for item in state.stack)


def test_appetite_with_no_expensive_cards_reveals_but_does_not_exile():
    state, spell_id, _ = _selective_state(
        "Appetite for Brains",
        "Target opponent reveals their hand. You choose a card from it with mana value 4 or greater and exile that card.",
    )
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": spell_id, "targets": {"target_player": 2},
    })
    assert resolve_top_of_stack(state)
    assert state.pending_mechanic_choice is None
    assert not state.players[2].exile
    assert any("reveals their hand: Forest" in line for line in state.log)


def test_appetite_fizzles_when_its_only_target_gains_hexproof():
    state, spell_id, _ = _selective_state(
        "Appetite for Brains",
        "Target opponent reveals their hand. You choose a card from it with mana value 4 or greater and exile that card.",
    )
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": spell_id, "targets": {"target_player": 2},
    })
    shield = CardInstance("shield", "Leyline of Sanctity", 2, 2, Zone.BATTLEFIELD, ["Enchantment"],
                          oracle_text="You have hexproof.")
    state.cards[shield.id] = shield
    state.players[2].battlefield.append(shield.id)
    assert resolve_top_of_stack(state)
    assert state.pending_mechanic_choice is None
    assert not state.players[2].exile
    assert not any("reveals their hand:" in line for line in state.log)


def test_ai_completes_revealed_exile_choice():
    state, spell_id, _ = _selective_state(
        "Appetite for Brains",
        "Target opponent reveals their hand. You choose a card from it with mana value 4 or greater and exile that card.",
    )
    expensive_id = state.players[2].hand[3]
    expensive = state.cards[expensive_id]
    expensive.name, expensive.types, expensive.type_line, expensive.mana_cost = (
        "Serra Angel", ["Creature"], "Creature - Angel", "{3}{W}{W}",
    )
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": spell_id, "targets": {"target_player": 2},
    })
    assert not resolve_top_of_stack(state)
    agent = AIAgent(difficulty="master", archetype="Midrange", opponent_archetype="Midrange")
    decision = agent.choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action == {"type": "choose_mechanic", "card_ids": [expensive_id]}
    state = checked_action(state, RulesEngine(), 1, decision.action)
    assert expensive_id in state.players[2].exile


def test_thoughtseize_loses_life_even_when_target_has_only_lands():
    state, spell_id, _ = _selective_state(
        "Thoughtseize",
        "Target player reveals their hand. You choose a nonland card from it. "
        "That player discards that card. You lose 2 life.",
    )
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": spell_id, "targets": {"target_player": 1},
    })
    assert resolve_top_of_stack(state)
    assert state.pending_mechanic_choice is None
    assert state.players[1].life == 18
    assert state.cards[spell_id].zone == Zone.GRAVEYARD


def test_thoughtseize_reveals_lands_and_loses_life_when_no_card_qualifies():
    state, spell_id = _state()
    spell = state.cards[spell_id]
    spell.name, spell.mana_cost = "Thoughtseize", "{B}"
    spell.oracle_text = (
        "Target player reveals their hand. You choose a nonland card from it. "
        "That player discards that card. You lose 2 life."
    )
    state.players[1].mana_pool = {"B": 1}
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": spell_id, "targets": {"target_player": 2},
    })
    assert resolve_top_of_stack(state)
    assert state.pending_mechanic_choice is None
    assert state.players[1].life == 18
    assert not state.players[2].graveyard
    assert any("reveals their hand: Swamp" in line for line in state.log)


def test_thoughtseize_does_not_lose_life_if_sole_target_turns_illegal():
    state, spell_id, _ = _selective_state(
        "Thoughtseize",
        "Target player reveals their hand. You choose a nonland card from it. "
        "That player discards that card. You lose 2 life.",
    )
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": spell_id, "targets": {"target_player": 2},
    })
    shield = CardInstance("shield", "Leyline of Sanctity", 2, 2, Zone.BATTLEFIELD, ["Enchantment"],
                          oracle_text="You have hexproof.")
    state.cards[shield.id] = shield
    state.players[2].battlefield.append(shield.id)
    assert resolve_top_of_stack(state)
    assert state.pending_mechanic_choice is None
    assert state.players[1].life == 20
    assert len(state.players[2].graveyard) == 0
    assert state.cards[spell_id].zone == Zone.GRAVEYARD
