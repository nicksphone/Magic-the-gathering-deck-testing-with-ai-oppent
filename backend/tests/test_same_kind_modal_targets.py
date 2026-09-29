from __future__ import annotations

import pytest

from ai.agent import AIAgent
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.zone_actions import put_into_graveyard


DESTROY = "Destroy target artifact"
DAMAGE = "Kolaghan's Command deals 2 damage to any target"
RETURN = "Return target creature card from your graveyard to your hand"
ORACLE = (
    "Choose two —\n"
    "• Return target creature card from your graveyard to your hand.\n"
    "• Target player discards a card.\n"
    "• Destroy target artifact.\n"
    "• Kolaghan's Command deals 2 damage to any target."
)


def _setup():
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=81)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    state.players[1].mana_pool = {"B": 1, "R": 1, "C": 1}
    spell_id = state.players[1].hand[0]
    spell = state.cards[spell_id]
    spell.name = "Kolaghan's Command"
    spell.types = ["Instant"]
    spell.type_line = "Instant"
    spell.mana_cost = "{1}{B}{R}"
    spell.oracle_text = ORACLE
    targets = (
        CardInstance("ring", "Sol Ring", 2, 2, Zone.BATTLEFIELD, ["Artifact"], oracle_text="{T}: Add {C}{C}."),
        CardInstance("bear", "Grizzly Bears", 2, 2, Zone.BATTLEFIELD, ["Creature"], power=2, toughness=2),
    )
    for card in targets:
        state.cards[card.id] = card
        state.players[2].battlefield.append(card.id)
    return state, spell_id


def test_ai_announces_distinct_targets_for_each_mode() -> None:
    state, spell_id = _setup()
    move = next(move for move in RulesEngine().legal_moves(state, 1)
                if move.get("type") == "cast_spell" and move.get("card_id") == spell_id)
    move["targets"] = {"mode_texts": [DESTROY, DAMAGE]}
    action = AIAgent(difficulty="master", archetype="Midrange")._materialize_action(state, move, 1)

    assert action["targets"]["mode_targets"] == {
        DESTROY: {"target_card_id": "ring"}, DAMAGE: {"target_card_id": "bear"},
    }
    assert checked_action(state, RulesEngine(), 1, action).stack[-1].source_card_id == spell_id


@pytest.mark.parametrize(
    ("remove_ring", "remove_bear", "resolves"),
    [(False, False, True), (True, False, True), (False, True, True), (True, True, False)],
)
def test_same_kind_modal_targets_resolve_independently(remove_ring: bool, remove_bear: bool, resolves: bool) -> None:
    state, spell_id = _setup()
    after = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": spell_id,
        "targets": {
            "mode_texts": [DESTROY, DAMAGE],
            "mode_targets": {DESTROY: {"target_card_id": "ring"}, DAMAGE: {"target_card_id": "bear"}},
        },
    })
    assert [(effect["effect_key"], effect["payload"].get("target_card_id")) for effect in after.stack[-1].payload["effects"]] == [
        ("destroy_permanent", "ring"), ("deal_damage", "bear"),
    ]
    if remove_ring:
        after.players[2].battlefield.remove("ring")
        put_into_graveyard(after, "ring")
    if remove_bear:
        after.players[2].battlefield.remove("bear")
        put_into_graveyard(after, "bear")

    assert resolve_top_of_stack(after)
    assert not after.stack
    assert "ring" in after.players[2].graveyard
    assert "bear" in after.players[2].graveyard
    assert ("Kolaghan's Command resolves." in after.log) is resolves


def _graveyard_pair():
    state, spell_id = _setup()
    for cid, name, owner in (("elf", "Llanowar Elves", 1), ("bear-own", "Grizzly Bears", 1), ("bear-opp", "Grizzly Bears", 2)):
        state.cards[cid] = CardInstance(cid, name, owner, owner, Zone.GRAVEYARD, ["Creature"])
        state.players[owner].graveyard.append(cid)
    return state, spell_id


def _return_and_destroy(spell_id: str, creature_id: str) -> dict:
    return {
        "type": "cast_spell", "card_id": spell_id,
        "targets": {
            "mode_texts": [RETURN, DESTROY],
            "mode_targets": {RETURN: {"target_card_id": creature_id}, DESTROY: {"target_card_id": "ring"}},
        },
    }


def test_return_mode_uses_announced_graveyard_card() -> None:
    state, spell_id = _graveyard_pair()
    after = checked_action(state, RulesEngine(), 1, _return_and_destroy(spell_id, "elf"))
    assert resolve_top_of_stack(after)
    assert "elf" in after.players[1].hand
    assert "bear-own" in after.players[1].graveyard
    assert "ring" in after.players[2].graveyard


def test_ai_selects_a_creature_in_its_own_graveyard() -> None:
    state, spell_id = _graveyard_pair()
    move = next(move for move in RulesEngine().legal_moves(state, 1)
                if move.get("type") == "cast_spell" and move.get("card_id") == spell_id)
    move["targets"] = {"mode_texts": [RETURN, DESTROY]}
    action = AIAgent(difficulty="master", archetype="Midrange")._materialize_action(state, move, 1)
    assert action["targets"]["mode_targets"][RETURN]["target_card_id"] in {"elf", "bear-own"}
    assert action["targets"]["mode_targets"][DESTROY]["target_card_id"] == "ring"
    assert checked_action(state, RulesEngine(), 1, action).stack[-1].source_card_id == spell_id


def test_return_mode_rejects_opponents_graveyard() -> None:
    state, spell_id = _graveyard_pair()
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, _return_and_destroy(spell_id, "bear-opp"))
    assert not state.stack
    assert spell_id in state.players[1].hand


def test_return_mode_can_fail_while_destroy_mode_resolves() -> None:
    state, spell_id = _graveyard_pair()
    after = checked_action(state, RulesEngine(), 1, _return_and_destroy(spell_id, "elf"))
    after = deserialize_match_snapshot(serialize_match_snapshot(after))
    assert after.stack[-1].payload["__announced_targets"]["mode_targets"][RETURN]["target_card_id"] == "elf"
    after.players[1].graveyard.remove("elf")
    after.players[1].exile.append("elf")
    after.cards["elf"].move_to_zone(Zone.EXILE)
    assert resolve_top_of_stack(after)
    assert "elf" in after.players[1].exile
    assert "ring" in after.players[2].graveyard
