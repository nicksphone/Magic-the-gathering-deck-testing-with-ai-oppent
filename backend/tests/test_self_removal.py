"""Winning self-removal uses actual costs, triggers and replacement rules."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.pending_effects import unanswered_action_wins
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_ineffective_destruction import settled_state
from tests.test_pending_removal import CARDS, add_card


@pytest.fixture(autouse=True)
def canonical_cards(monkeypatch):
    for filename in ["ineffective_destruction.json", "self_removal.json"]:
        for row in json.loads((Path(__file__).parent / "fixtures" / filename).read_text()):
            monkeypatch.setitem(CARDS, row["name"], row)


def winning_state(opponent_life=1):
    state, _, _ = settled_state()
    add_card(state, "Bastion of Remembrance", Zone.BATTLEFIELD)
    creature = add_card(state, "Sprite Dragon", Zone.BATTLEFIELD)
    murder = add_card(state, "Murder", Zone.HAND)
    state.players[2].life = opponent_life
    return state, creature, murder


@pytest.mark.parametrize("archetype", ["Drain", "Aristocrats", "Midrange", "Tempo", "Control"])
@pytest.mark.parametrize("difficulty", ["casual", "strong", "master"])
def test_ai_commits_winning_self_removal_across_styles(archetype, difficulty):
    state, creature, murder = winning_state()
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    before = serialize_match_snapshot(state)
    decision = AIAgent(archetype=archetype, difficulty=difficulty).choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action["card_id"] == murder.id
    assert decision.action["targets"]["target_card_id"] == creature.id
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, RulesEngine(), 1, decision.action)
    while state.stack and state.winner is None:
        RulesEngine().take_action(state, state.priority_player, {"type": "pass_priority"})
    assert state.winner == 1
    assert state.players[2].life == 0


def test_nonwinning_self_removal_remains_conserved():
    state, _, murder = winning_state(opponent_life=2)
    decision = AIAgent(archetype="Drain").choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action.get("card_id") != murder.id


def test_exile_replacement_blocks_assumed_death_win():
    state, creature, murder = winning_state()
    add_card(state, "Leyline of the Void", Zone.BATTLEFIELD, 2)
    assert unanswered_action_wins(state, 1, {
        "type": "cast_spell", "card_id": murder.id, "targets": {"target_card_id": creature.id},
    }) is False
    decision = AIAgent(archetype="Drain").choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action.get("card_id") != murder.id


def test_projection_does_not_waive_mana_cost():
    state, creature, murder = winning_state()
    state.players[1].mana_pool = {"U": 10}
    before = serialize_match_snapshot(state)
    assert unanswered_action_wins(state, 1, {
        "type": "cast_spell", "card_id": murder.id, "targets": {"target_card_id": creature.id},
    }) is False
    assert serialize_match_snapshot(state) == before


def test_projection_does_not_waive_indestructible_for_a_death_payoff():
    state, _, murder = winning_state()
    creature = add_card(state, "Darksteel Myr", Zone.BATTLEFIELD)
    assert unanswered_action_wins(state, 1, {
        "type": "cast_spell", "card_id": murder.id, "targets": {"target_card_id": creature.id},
    }) is False


def test_unknown_opponent_death_trigger_choice_is_not_assumed_harmless():
    state, creature, murder = winning_state()
    add_card(state, "Blood Artist", Zone.BATTLEFIELD, 2)
    assert unanswered_action_wins(state, 1, {
        "type": "cast_spell", "card_id": murder.id, "targets": {"target_card_id": creature.id},
    }) is None


def test_own_death_target_choices_use_the_ai_policy_to_find_a_winning_line():
    state, creature, murder = winning_state()
    add_card(state, "Blood Artist", Zone.BATTLEFIELD)
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    ai = AIAgent(archetype="Aristocrats", difficulty="master")
    before = serialize_match_snapshot(state)
    decision = ai.choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action["card_id"] == murder.id
    assert decision.action["targets"]["target_card_id"] == creature.id
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, RulesEngine(), 1, decision.action)
    for _ in range(40):
        if state.winner is not None:
            break
        choice = state.pending_trigger_order or state.pending_mechanic_choice or state.pending_replacement_choice
        pid = choice.get("player_id", choice.get("current_controller")) if choice else state.priority_player
        action = ai.choose_action(state, RulesEngine().legal_moves(state, pid), pid).action if choice else {"type": "pass_priority"}
        state = checked_action(state, RulesEngine(), pid, action)
    assert state.winner == 1


def test_hidden_library_movement_does_not_certify_a_projected_outcome():
    state, _, _ = winning_state()
    artifact = add_card(state, "Mind Stone", Zone.BATTLEFIELD)
    spell = add_card(state, "Slice in Twain", Zone.HAND)
    before = serialize_match_snapshot(state)
    assert unanswered_action_wins(state, 1, {
        "type": "cast_spell", "card_id": spell.id, "targets": {"target_card_id": artifact.id},
    }) is None
    assert serialize_match_snapshot(state) == before


def test_sacrifice_value_preserves_recurring_drain_not_spent_entry_token():
    state, creature, _ = winning_state()
    artist = add_card(state, "Blood Artist", Zone.BATTLEFIELD)
    bastion = next(cid for cid in state.players[1].battlefield if state.cards[cid].name == "Bastion of Remembrance")
    ai = AIAgent(archetype="Aristocrats")
    assert ai._sacrifice_loss(state, artist.id, 1) > ai._sacrifice_loss(state, creature.id, 1)
    assert ai._sacrifice_loss(state, bastion, 1) == pytest.approx(5 + 3 * 0.6 + 1 + 6)


def test_sacrifice_activation_cost_can_supply_the_winning_death():
    state, _, _ = settled_state()
    bastion = add_card(state, "Bastion of Remembrance", Zone.BATTLEFIELD)
    brontodon = add_card(state, "Thrashing Brontodon", Zone.BATTLEFIELD)
    state.players[2].life = 1
    decision = AIAgent(archetype="Aristocrats").choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action["type"] == "activate_ability"
    assert decision.action["card_id"] == brontodon.id
    assert decision.action["targets"]["target_card_id"] == bastion.id
    state = checked_action(state, RulesEngine(), 1, decision.action)
    while state.stack and state.winner is None:
        RulesEngine().take_action(state, state.priority_player, {"type": "pass_priority"})
    assert state.winner == 1
    assert state.cards[brontodon.id].zone == Zone.GRAVEYARD


def test_loyalty_can_use_the_same_winning_self_removal_path():
    state, _, _ = settled_state()
    add_card(state, "Bastion of Remembrance", Zone.BATTLEFIELD)
    creature = add_card(state, "Sprite Dragon", Zone.BATTLEFIELD)
    raw = CARDS["Vraska the Unseen"]
    source = CardInstance("vraska", raw["name"], 1, 1, Zone.BATTLEFIELD, ["Planeswalker"],
                          mana_cost=raw["mana_cost"], oracle_text=raw["oracle_text"],
                          type_line=raw["type_line"], colors=raw["colors"], loyalty=int(raw["loyalty"]))
    state.cards[source.id] = source
    state.players[1].battlefield.append(source.id)
    state.players[2].life = 1
    decision = AIAgent(archetype="Midrange").choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action["type"] == "activate_loyalty"
    assert decision.action["targets"]["target_card_id"] == creature.id
    state = checked_action(state, RulesEngine(), 1, decision.action)
    while state.stack and state.winner is None:
        RulesEngine().take_action(state, state.priority_player, {"type": "pass_priority"})
    assert state.winner == 1
    assert state.cards[source.id].loyalty == int(raw["loyalty"]) - 3
