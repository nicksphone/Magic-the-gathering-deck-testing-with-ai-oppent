from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from ai.agent import AIAgent
from game_state.serializers import deserialize_match_snapshot, serialize_card_view, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine import combat
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from main import ACTIVE_MATCHES, MatchController, _persist_active_match, app
from persistence.db import engine as db_engine
from persistence.repository import Repository


def _state():
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=73)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.DECLARE_BLOCKERS
    state.blockers_declared = True
    state.mechanic_choice_players = {1, 2}
    return state


def _creature(state, cid: str, owner: int, name: str, power: int, toughness: int, keywords=(), oracle_text="") -> None:
    card = CardInstance(
        id=cid, name=name, owner=owner, controller=owner, zone=Zone.BATTLEFIELD,
        types=["Creature"], power=power, toughness=toughness,
        keywords=list(keywords), oracle_text=oracle_text, summoning_sick=False,
    )
    state.cards[cid] = card
    state.players[owner].battlefield.append(cid)


def _enter_damage(state) -> None:
    engine = RulesEngine()
    engine.take_action(state, 1, {"type": "pass_priority"})
    engine.take_action(state, 2, {"type": "pass_priority"})
    assert state.step == Step.COMBAT_DAMAGE


def _finish_shared_blocker_choice(state):
    pending = state.pending_mechanic_choice
    assert pending["player_id"] == 2
    assert pending["kind"] == "combat_damage"
    assert state.players[2].life == 20
    amounts = {cid: 0 for cid in pending["options"]}
    amounts[pending["options"][0]] = pending["count"]
    return checked_action(state, RulesEngine(), 2, {
        "type": "choose_mechanic", "damage_assignment": amounts,
    })


def test_simultaneous_combat_deaths_use_shared_state_actions() -> None:
    state = _state()
    state.mechanic_choice_players = set()
    _creature(state, "courser", 1, "Centaur Courser", 3, 3)
    _creature(state, "giant", 2, "Hill Giant", 3, 3)
    state.attackers = ["courser"]
    state.blocks = {"courser": ["giant"]}

    combat.combat_damage(state)

    assert state.cards["courser"].zone == Zone.GRAVEYARD
    assert state.cards["giant"].zone == Zone.GRAVEYARD
    assert sum("State-based action:" in line for line in state.log) == 2
    assert not state.trigger_staging


def test_multi_blocked_attacker_can_assign_all_damage_to_later_blocker_after_snapshot() -> None:
    state = _state()
    _creature(state, "courser", 1, "Centaur Courser", 3, 3)
    _creature(state, "bears", 2, "Grizzly Bears", 2, 2)
    _creature(state, "giant", 2, "Hill Giant", 3, 3)
    state.attackers = ["courser"]
    state.blocks = {"courser": ["bears", "giant"]}

    _enter_damage(state)
    assert state.pending_mechanic_choice["player_id"] == 1
    assert state.cards["giant"].zone == Zone.BATTLEFIELD
    assert state.cards["giant"].counters.get("__damage_marked", 0) == 0
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {
            "type": "choose_mechanic", "damage_assignment": {"bears": 2, "giant": 2},
        })
    assert serialize_match_snapshot(state) == before

    state = checked_action(state, RulesEngine(), 1, {
        "type": "choose_mechanic", "damage_assignment": {"bears": 0, "giant": 3},
    })
    assert state.pending_mechanic_choice is None
    assert state.cards["bears"].zone == Zone.BATTLEFIELD
    assert state.cards["giant"].zone == Zone.GRAVEYARD
    assert state.cards["courser"].zone == Zone.GRAVEYARD


def test_palace_guard_controller_chooses_which_attacker_takes_its_one_damage() -> None:
    state = _state()
    _creature(state, "elves", 1, "Llanowar Elves", 1, 1)
    _creature(state, "mystic", 1, "Elvish Mystic", 1, 1)
    _creature(state, "guard", 2, "Palace Guard", 1, 4, oracle_text="Palace Guard can block any number of creatures.")
    state.attackers = ["elves", "mystic"]
    combat.declare_blockers(state, {"elves": ["guard"], "mystic": ["guard"]})
    _enter_damage(state)
    assert state.pending_mechanic_choice["player_id"] == 2
    assert state.priority_player == 2
    assert state.players[2].life == 20
    state = checked_action(state, RulesEngine(), 2, {
        "type": "choose_mechanic", "damage_assignment": {"elves": 0, "mystic": 1},
    })
    assert state.cards["elves"].zone == Zone.BATTLEFIELD
    assert state.cards["mystic"].zone == Zone.GRAVEYARD
    assert state.cards["guard"].zone == Zone.BATTLEFIELD


def test_trample_player_damage_triggers_ohran_frostfang() -> None:
    state = _state()
    state.mechanic_choice_players = set()
    _creature(state, "frostfang", 1, "Ohran Frostfang", 2, 6,
              oracle_text="Attacking creatures you control have deathtouch.\nWhenever a creature you control deals combat damage to a player, draw a card.")
    _creature(state, "monstrosaur", 1, "Charging Monstrosaur", 5, 5, keywords=["trample", "haste"])
    _creature(state, "bears", 2, "Grizzly Bears", 2, 2)
    state.attackers = ["monstrosaur"]
    state.blocks = {"monstrosaur": ["bears"]}

    combat.combat_damage(state)

    assert state.players[2].life < 20
    assert any(item.source_card_id == "frostfang" for item in state.stack)


def test_other_creatures_combat_damage_does_not_trigger_shadowmage_infiltrator() -> None:
    state = _state()
    state.mechanic_choice_players = set()
    _creature(state, "infiltrator", 1, "Shadowmage Infiltrator", 1, 3,
              oracle_text="Fear\nWhenever this creature deals combat damage to a player, you may draw a card.")
    _creature(state, "bears", 1, "Grizzly Bears", 2, 2)
    state.attackers = ["bears"]

    combat.combat_damage(state)

    assert state.players[2].life == 18
    assert not any(item.source_card_id == "infiltrator" for item in state.stack)


def test_shadowmage_infiltrator_still_triggers_on_its_own_combat_damage() -> None:
    state = _state()
    state.mechanic_choice_players = set()
    _creature(state, "infiltrator", 1, "Shadowmage Infiltrator", 1, 3,
              oracle_text="Fear\nWhenever this creature deals combat damage to a player, you may draw a card.")
    state.attackers = ["infiltrator"]

    combat.combat_damage(state)

    assert state.players[2].life == 19
    assert any(item.source_card_id == "infiltrator" for item in state.stack)


def test_blocker_damage_emits_combat_event_with_actual_amount() -> None:
    state = _state()
    state.mechanic_choice_players = set()
    _creature(state, "courser", 1, "Centaur Courser", 3, 3)
    _creature(state, "bears", 2, "Grizzly Bears", 2, 2)
    state.attackers = ["courser"]
    state.blocks = {"courser": ["bears"]}

    with patch.object(combat, "emit_event_batch", wraps=combat.emit_event_batch) as emitted:
        combat.combat_damage(state)

    assert any(call.args[1] == "combat_damage_dealt" and
               {"source_card_id": "bears", "target_card_id": "courser", "amount": 2} in call.args[2]
               for call in emitted.call_args_list)


def test_simultaneous_player_hits_offer_one_trigger_order_choice() -> None:
    state = _state()
    state.mechanic_choice_players = set()
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1}
    _creature(state, "frostfang", 1, "Ohran Frostfang", 2, 6,
              oracle_text="Attacking creatures you control have deathtouch.\nWhenever a creature you control deals combat damage to a player, draw a card.")
    _creature(state, "bears", 1, "Grizzly Bears", 2, 2)
    _creature(state, "courser", 1, "Centaur Courser", 3, 3)
    state.attackers = ["bears", "courser"]

    combat.combat_damage(state)

    assert state.players[2].life == 15
    assert state.pending_trigger_order is not None
    assert state.pending_trigger_order["event"] == "combat_damage_step"
    assert len(state.pending_trigger_order["groups"]["1"]) == 2
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    order = next(move["trigger_order"] for move in RulesEngine().legal_moves(state, 1)
                 if move["type"] == "choose_trigger_order")
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_trigger_order", "trigger_order": order})
    assert state.pending_trigger_order is None
    assert sum(item.source_card_id == "frostfang" for item in state.stack) == 2


def test_damage_and_death_triggers_share_one_order_choice() -> None:
    state = _state()
    state.mechanic_choice_players = set()
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1}
    _creature(state, "frostfang", 1, "Ohran Frostfang", 2, 6,
              oracle_text="Attacking creatures you control have deathtouch.\nWhenever a creature you control deals combat damage to a player, draw a card.")
    _creature(state, "haruspex", 1, "Grim Haruspex", 3, 2,
              oracle_text="Morph {B}\nWhenever another nontoken creature you control dies, draw a card.")
    _creature(state, "bears", 1, "Grizzly Bears", 2, 2)
    _creature(state, "courser", 1, "Centaur Courser", 3, 3)
    _creature(state, "giant", 2, "Hill Giant", 3, 3)
    state.attackers = ["bears", "courser"]
    state.blocks = {"courser": ["giant"]}

    combat.combat_damage(state)

    assert state.pending_trigger_order is not None
    assert len(state.pending_trigger_order["groups"]["1"]) == 2


def test_combat_damage_triggers_from_both_controllers_use_apnap_order() -> None:
    state = _state()
    state.mechanic_choice_players = set()
    _creature(state, "frostfang", 1, "Ohran Frostfang", 2, 6,
              oracle_text="Attacking creatures you control have deathtouch.\nWhenever a creature you control deals combat damage to a player, draw a card.")
    _creature(state, "bears", 1, "Grizzly Bears", 2, 2)
    _creature(state, "courser", 1, "Centaur Courser", 3, 3)
    _creature(state, "phage", 2, "Phage the Untouchable", 4, 4,
              oracle_text="Whenever Phage deals combat damage to a creature, destroy that creature. It can't be regenerated.")
    state.attackers = ["bears", "courser"]
    state.blocks = {"courser": ["phage"]}

    combat.combat_damage(state)

    assert [item.source_card_id for item in state.stack] == ["frostfang", "phage"]


def test_staged_combat_triggers_survive_snapshot_before_flush() -> None:
    state = _state()
    state.trigger_staging = True
    _creature(state, "frostfang", 1, "Ohran Frostfang", 2, 6,
              oracle_text="Attacking creatures you control have deathtouch.\nWhenever a creature you control deals combat damage to a player, draw a card.")
    _creature(state, "bears", 1, "Grizzly Bears", 2, 2)
    from rules_engine.events import emit_event
    emit_event(state, "combat_damage_dealt", {"source_card_id": "bears", "target_player": 2, "amount": 2})
    assert not state.stack
    state.pending_replacement_choice = {"resume_kind": "combat_die", "player_id": 1}
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert state.trigger_staging and len(state.staged_triggers) == 1

    from rules_engine.state_based_actions import apply_state_based_actions
    apply_state_based_actions(state)
    assert state.trigger_staging and not state.stack
    state.pending_replacement_choice = None
    apply_state_based_actions(state)

    assert not state.trigger_staging
    assert not state.staged_triggers
    assert [item.source_card_id for item in state.stack] == ["frostfang"]


def test_doomed_traveler_own_death_trigger_survives_combat_zone_change() -> None:
    state = _state()
    state.mechanic_choice_players = set()
    _creature(state, "courser", 1, "Centaur Courser", 3, 3)
    _creature(state, "traveler", 2, "Doomed Traveler", 1, 1,
              oracle_text="When this creature dies, create a 1/1 white Spirit creature token with flying.")
    state.attackers = ["courser"]
    state.blocks = {"courser": ["traveler"]}

    combat.combat_damage(state)

    assert state.cards["traveler"].zone == Zone.GRAVEYARD
    assert any(item.source_card_id == "traveler" for item in state.stack)
    from rules_engine.stack_engine import resolve_top_of_stack
    resolve_top_of_stack(state)
    spirits = [state.cards[cid] for cid in state.players[2].battlefield if state.cards[cid].name == "Spirit"]
    assert len(spirits) == 1
    assert (spirits[0].power, spirits[0].toughness) == (1, 1)
    assert "flying" in spirits[0].keywords
    assert spirits[0].colors == ["W"]
    assert serialize_card_view(state, spirits[0].id)["colors"] == ["W"]
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert state.cards[spirits[0].id].colors == ["W"]


def test_doomed_traveler_own_death_trigger_survives_state_based_action() -> None:
    state = _state()
    _creature(state, "traveler", 1, "Doomed Traveler", 1, 1,
              oracle_text="When this creature dies, create a 1/1 white Spirit creature token with flying.")
    state.cards["traveler"].counters["__damage_marked"] = 1

    from rules_engine.state_based_actions import apply_state_based_actions
    apply_state_based_actions(state)

    assert state.cards["traveler"].zone == Zone.GRAVEYARD
    assert any(item.source_card_id == "traveler" for item in state.stack)


def test_all_attackers_use_pre_damage_power_when_first_hit_changes_a_continuous_value() -> None:
    state = _state()
    _creature(state, "first", 1, "Centaur Courser", 3, 3)
    _creature(state, "second", 1, "Grizzly Bears", 2, 2)
    state.attackers = ["first", "second"]
    original_power = combat.effective_power

    def life_scaled_power(current_state, card_id):
        if card_id == "second":
            return 22 - current_state.players[2].life
        return original_power(current_state, card_id)

    with patch.object(combat, "effective_power", side_effect=life_scaled_power):
        combat._combat_damage_step(state, 2, set(), first_strike_only=False)
    assert state.players[2].life == 15


def test_trample_cannot_spill_before_assigning_lethal_to_blocker() -> None:
    state = _state()
    _creature(state, "monstrosaur", 1, "Charging Monstrosaur", 5, 5, ["trample", "haste"])
    _creature(state, "bears", 2, "Grizzly Bears", 2, 2)
    state.attackers = ["monstrosaur"]
    state.blocks = {"monstrosaur": ["bears"]}
    _enter_damage(state)
    assert state.pending_mechanic_choice["options"] == ["bears", "player:2"]
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {
            "type": "choose_mechanic", "damage_assignment": {"bears": 1, "player:2": 4},
        })
    assert state.players[2].life == 20
    state = checked_action(state, RulesEngine(), 1, {
        "type": "choose_mechanic", "damage_assignment": {"bears": 2, "player:2": 3},
    })
    assert state.cards["bears"].zone == Zone.GRAVEYARD
    assert state.players[2].life == 17


def test_trample_counts_another_attacker_assigned_to_the_same_palace_guard() -> None:
    state = _state()
    _creature(state, "elf", 1, "Llanowar Elves", 1, 1)
    _creature(state, "trampler", 1, "Charging Monstrosaur", 5, 5, ["trample", "haste"])
    _creature(state, "guard", 2, "Palace Guard", 1, 4, oracle_text="Palace Guard can block any number of creatures.")
    state.attackers = ["elf", "trampler"]
    combat.declare_blockers(state, {"elf": ["guard"], "trampler": ["guard"]})
    _enter_damage(state)
    state = checked_action(state, RulesEngine(), 1, {
        "type": "choose_mechanic", "damage_assignment": {"guard": 3, "player:2": 2},
    })
    state = _finish_shared_blocker_choice(state)
    assert state.cards["guard"].zone == Zone.GRAVEYARD
    assert state.players[2].life == 18


def test_two_tramplers_are_validated_as_one_controller_assignment_and_can_restart() -> None:
    state = _state()
    _creature(state, "first", 1, "Charging Monstrosaur", 5, 5, ["trample", "haste"])
    _creature(state, "second", 1, "Charging Monstrosaur", 5, 5, ["trample", "haste"])
    _creature(state, "guard", 2, "Palace Guard", 1, 4, oracle_text="Palace Guard can block any number of creatures.")
    state.attackers = ["first", "second"]
    combat.declare_blockers(state, {"first": ["guard"], "second": ["guard"]})
    _enter_damage(state)
    state = checked_action(state, RulesEngine(), 1, {
        "type": "choose_mechanic", "damage_assignment": {"guard": 0, "player:2": 5},
    })
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert state.pending_mechanic_choice["source_id"] == "second"
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {
            "type": "choose_mechanic", "damage_assignment": {"guard": 3, "player:2": 2},
        })
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, RulesEngine(), 1, {
        "type": "choose_mechanic", "choice_id": "restart",
    })
    assert state.pending_mechanic_choice["source_id"] == "first"
    state = checked_action(state, RulesEngine(), 1, {
        "type": "choose_mechanic", "damage_assignment": {"guard": 1, "player:2": 4},
    })
    state = checked_action(state, RulesEngine(), 1, {
        "type": "choose_mechanic", "damage_assignment": {"guard": 3, "player:2": 2},
    })
    state = _finish_shared_blocker_choice(state)
    assert state.cards["guard"].zone == Zone.GRAVEYARD
    assert state.players[2].life == 14


def test_other_attacker_deathtouch_assignment_satisfies_trample_lethal() -> None:
    state = _state()
    _creature(state, "rats", 1, "Typhoid Rats", 1, 1, ["deathtouch"])
    _creature(state, "trampler", 1, "Charging Monstrosaur", 5, 5, ["trample", "haste"])
    _creature(state, "guard", 2, "Palace Guard", 1, 4, oracle_text="Palace Guard can block any number of creatures.")
    state.attackers = ["rats", "trampler"]
    combat.declare_blockers(state, {"rats": ["guard"], "trampler": ["guard"]})
    _enter_damage(state)
    state = checked_action(state, RulesEngine(), 1, {
        "type": "choose_mechanic", "damage_assignment": {"guard": 0, "player:2": 5},
    })
    state = _finish_shared_blocker_choice(state)
    assert state.cards["guard"].zone == Zone.GRAVEYARD
    assert state.players[2].life == 15


def test_ai_second_trampler_spills_after_first_assigned_lethal_to_shared_blocker() -> None:
    state = _state()
    _creature(state, "first", 1, "Charging Monstrosaur", 5, 5, ["trample", "haste"])
    _creature(state, "second", 1, "Charging Monstrosaur", 5, 5, ["trample", "haste"])
    _creature(state, "guard", 2, "Palace Guard", 1, 4, oracle_text="Palace Guard can block any number of creatures.")
    state.attackers = ["first", "second"]
    combat.declare_blockers(state, {"first": ["guard"], "second": ["guard"]})
    _enter_damage(state)
    agent = AIAgent(difficulty="master")
    engine = RulesEngine()
    first = agent.choose_action(state, engine.legal_moves(state, 1), 1).action
    assert first["damage_assignment"] == {"guard": 4, "player:2": 1}
    state = checked_action(state, engine, 1, first)
    second = agent.choose_action(state, engine.legal_moves(state, 1), 1).action
    assert second["damage_assignment"] == {"guard": 0, "player:2": 5}
    state = checked_action(state, engine, 1, second)
    state = _finish_shared_blocker_choice(state)
    assert state.players[2].life == 14


def test_banding_blocker_lets_defender_assign_attackers_damage() -> None:
    state = _state()
    _creature(state, "courser", 1, "Centaur Courser", 3, 3)
    _creature(state, "hero", 2, "Benalish Hero", 1, 1, ["banding"])
    _creature(state, "bears", 2, "Grizzly Bears", 2, 2)
    state.attackers = ["courser"]
    combat.declare_blockers(state, {"courser": ["hero", "bears"]})
    _enter_damage(state)
    assert state.pending_mechanic_choice["player_id"] == 2
    assert state.priority_player == 2
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {
            "type": "choose_mechanic", "damage_assignment": {"hero": 3, "bears": 0},
        })
    state = checked_action(state, RulesEngine(), 2, {
        "type": "choose_mechanic", "damage_assignment": {"hero": 3, "bears": 0},
    })
    assert state.cards["hero"].zone == Zone.GRAVEYARD
    assert state.cards["bears"].zone == Zone.BATTLEFIELD


def test_banding_attacker_lets_active_player_assign_multi_blockers_damage() -> None:
    state = _state()
    _creature(state, "hero", 1, "Benalish Hero", 1, 1, ["banding"])
    _creature(state, "elf", 1, "Llanowar Elves", 1, 1)
    _creature(state, "guard", 2, "Palace Guard", 1, 4, oracle_text="Palace Guard can block any number of creatures.")
    state.attackers = ["hero", "elf"]
    combat.declare_blockers(state, {"hero": ["guard"], "elf": ["guard"]})
    _enter_damage(state)
    assert state.pending_mechanic_choice["player_id"] == 1
    assert state.priority_player == 1
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 2, {
            "type": "choose_mechanic", "damage_assignment": {"hero": 0, "elf": 1},
        })
    state = checked_action(state, RulesEngine(), 1, {
        "type": "choose_mechanic", "damage_assignment": {"hero": 0, "elf": 1},
    })
    assert state.cards["hero"].zone == Zone.BATTLEFIELD
    assert state.cards["elf"].zone == Zone.GRAVEYARD


def test_ai_defender_with_banding_blocks_trample_to_life() -> None:
    state = _state()
    _creature(state, "trampler", 1, "Charging Monstrosaur", 5, 5, ["trample", "haste"])
    _creature(state, "hero", 2, "Benalish Hero", 1, 1, ["banding"])
    state.attackers = ["trampler"]
    combat.declare_blockers(state, {"trampler": ["hero"]})
    _enter_damage(state)
    assert state.pending_mechanic_choice["player_id"] == 2
    decision = AIAgent(difficulty="master").choose_action(state, RulesEngine().legal_moves(state, 2), 2)
    assert decision.action["damage_assignment"] == {"hero": 5, "player:2": 0}
    state = checked_action(state, RulesEngine(), 2, decision.action)
    assert state.players[2].life == 20


def test_restart_preserves_other_players_banding_damage_assignment() -> None:
    state = _state()
    _creature(state, "courser", 1, "Centaur Courser", 3, 3)
    _creature(state, "first", 1, "Charging Monstrosaur", 5, 5, ["trample", "haste"])
    _creature(state, "second", 1, "Charging Monstrosaur", 5, 5, ["trample", "haste"])
    _creature(state, "hero", 2, "Benalish Hero", 1, 1, ["banding"])
    _creature(state, "bears", 2, "Grizzly Bears", 2, 2)
    _creature(state, "guard", 2, "Palace Guard", 1, 4, oracle_text="Palace Guard can block any number of creatures.")
    state.attackers = ["courser", "first", "second"]
    combat.declare_blockers(state, {
        "courser": ["hero", "bears"], "first": ["guard"], "second": ["guard"],
    })
    _enter_damage(state)
    assert state.pending_mechanic_choice["player_id"] == 2
    state = checked_action(state, RulesEngine(), 2, {
        "type": "choose_mechanic", "damage_assignment": {"hero": 3, "bears": 0},
    })
    assert state.pending_mechanic_choice["source_id"] == "first"
    assert state.pending_mechanic_choice["can_restart"] is False
    state = checked_action(state, RulesEngine(), 1, {
        "type": "choose_mechanic", "damage_assignment": {"guard": 4, "player:2": 1},
    })
    assert state.pending_mechanic_choice["source_id"] == "second"
    assert state.pending_mechanic_choice["can_restart"] is True
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "choice_id": "restart"})
    assert state.pending_mechanic_choice["source_id"] == "first"
    assert state.combat_damage_assignments == {"courser": {"hero": 3, "bears": 0}}
    assert state.priority_player == 1


def test_trample_assignment_to_planeswalker_reduces_loyalty() -> None:
    state = _state()
    _creature(state, "monstrosaur", 1, "Charging Monstrosaur", 5, 5, ["trample", "haste"])
    _creature(state, "bears", 2, "Grizzly Bears", 2, 2)
    walker = CardInstance(
        id="teferi", name="Teferi, Hero of Dominaria", owner=2, controller=2,
        zone=Zone.BATTLEFIELD, types=["Planeswalker"], loyalty=4,
    )
    state.cards[walker.id] = walker
    state.players[2].battlefield.append(walker.id)
    state.attackers = ["monstrosaur"]
    state.attack_targets = {"monstrosaur": "planeswalker:teferi"}
    state.blocks = {"monstrosaur": ["bears"]}
    _enter_damage(state)
    pending = state.pending_mechanic_choice
    assert pending["options"] == ["bears", "planeswalker:teferi"]
    assert pending["option_labels"]["planeswalker:teferi"] == walker.name
    state = checked_action(state, RulesEngine(), 1, {
        "type": "choose_mechanic", "damage_assignment": {"bears": 2, "planeswalker:teferi": 3},
    })
    assert state.cards["teferi"].loyalty == 1
    assert state.players[2].life == 20


def test_double_strike_requests_fresh_assignment_in_regular_step() -> None:
    state = _state()
    _creature(state, "swiftblade", 1, "Boros Swiftblade", 1, 2, ["double strike"])
    _creature(state, "omens", 2, "Wall of Omens", 0, 4)
    _creature(state, "runes", 2, "Wall of Runes", 0, 4)
    state.attackers = ["swiftblade"]
    state.blocks = {"swiftblade": ["omens", "runes"]}
    _enter_damage(state)
    assert state.combat_damage_stage == "first"
    state = checked_action(state, RulesEngine(), 1, {
        "type": "choose_mechanic", "damage_assignment": {"omens": 1, "runes": 0},
    })
    assert state.cards["omens"].counters["__damage_marked"] == 1
    engine = RulesEngine()
    engine.take_action(state, 1, {"type": "pass_priority"})
    engine.take_action(state, 2, {"type": "pass_priority"})
    assert state.combat_damage_stage == "regular"
    assert state.pending_mechanic_choice["options"] == ["omens", "runes"]
    state = checked_action(state, RulesEngine(), 1, {
        "type": "choose_mechanic", "damage_assignment": {"omens": 0, "runes": 1},
    })
    assert state.cards["omens"].counters["__damage_marked"] == 1
    assert state.cards["runes"].counters["__damage_marked"] == 1


def test_ai_prioritizes_killing_more_threatening_blocker() -> None:
    state = _state()
    _creature(state, "courser", 1, "Centaur Courser", 3, 3)
    _creature(state, "bears", 2, "Grizzly Bears", 2, 2)
    _creature(state, "giant", 2, "Hill Giant", 3, 3)
    state.attackers = ["courser"]
    state.blocks = {"courser": ["bears", "giant"]}
    _enter_damage(state)
    decision = AIAgent(difficulty="master").choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action == {"type": "choose_mechanic", "damage_assignment": {"bears": 0, "giant": 3}}


def test_damage_choice_rejects_wrong_actor_unknown_recipient_and_stale_step() -> None:
    state = _state()
    _creature(state, "courser", 1, "Centaur Courser", 3, 3)
    _creature(state, "bears", 2, "Grizzly Bears", 2, 2)
    _creature(state, "giant", 2, "Hill Giant", 3, 3)
    state.attackers = ["courser"]
    state.blocks = {"courser": ["bears", "giant"]}
    _enter_damage(state)
    original = serialize_match_snapshot(state)
    for actor, amounts in (
        (2, {"bears": 0, "giant": 3}),
        (1, {"bears": -1, "giant": 4}),
        (1, {"bears": 0, "giant": 3, "player:2": 0}),
        (1, {"bears": 0}),
    ):
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), actor, {"type": "choose_mechanic", "damage_assignment": amounts})
        assert serialize_match_snapshot(state) == original
    state.step = Step.END_COMBAT
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {
            "type": "choose_mechanic", "damage_assignment": {"bears": 0, "giant": 3},
        })


def test_http_damage_choice_rejects_bad_split_without_mutating_saved_match() -> None:
    state = _state()
    _creature(state, "courser", 1, "Centaur Courser", 3, 3)
    _creature(state, "bears", 2, "Grizzly Bears", 2, 2)
    _creature(state, "giant", 2, "Hill Giant", 3, 3)
    state.attackers = ["courser"]
    state.blocks = {"courser": ["bears", "giant"]}
    _enter_damage(state)
    deck = [{"quantity": 60, "card_name": "Island"}]
    match = MatchController(
        state=state, rules=RulesEngine(), controllers={1: "human", 2: "human"},
        ai={1: AIAgent(), 2: AIAgent()}, mode="human_vs_human",
        deck_ids=(None, None), mainboards={1: deck, 2: deck}, sideboards={1: [], 2: []},
        game_number=1, current_game_recorded=False, match_complete=False, best_of=3,
    )
    with TestClient(app) as client:
        ACTIVE_MATCHES[state.id] = match
        try:
            with Session(db_engine) as session:
                repo = Repository(session)
                _persist_active_match(repo, match)
                before_saved = repo.get_active_match(state.id).state_json
            before_memory = serialize_match_snapshot(match.state)
            legal = client.get(f"/matches/{state.id}/legal-moves")
            assert legal.status_code == 200
            assert legal.json()["moves"][0]["kind"] == "combat_damage"
            autoplay = client.post(f"/matches/{state.id}/autoplay", params={"ticks": 5})
            assert autoplay.status_code == 200
            assert autoplay.json()["pending_mechanic_choice"]["source_id"] == "courser"
            assert serialize_match_snapshot(match.state) == before_memory

            invalid = client.post(f"/matches/{state.id}/action", json={
                "player_id": 1, "action": {"type": "choose_mechanic", "damage_assignment": {"bears": 2, "giant": 2}},
            })
            assert invalid.status_code == 422
            assert serialize_match_snapshot(match.state) == before_memory
            with Session(db_engine) as session:
                assert Repository(session).get_active_match(state.id).state_json == before_saved

            valid = client.post(f"/matches/{state.id}/action", json={
                "player_id": 1, "action": {"type": "choose_mechanic", "damage_assignment": {"bears": 0, "giant": 3}},
            })
            assert valid.status_code == 200, valid.text
            assert valid.json()["pending_mechanic_choice"] is None
            assert not any(card["id"] == "giant" for card in valid.json()["players"]["2"]["battlefield"])
        finally:
            ACTIVE_MATCHES.pop(state.id, None)
