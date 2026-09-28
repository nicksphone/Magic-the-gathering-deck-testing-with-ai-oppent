from __future__ import annotations

import pytest

from ai.agent import AIAgent
from effects.handlers import deal_damage
from game_state.state import CardInstance, MatchFactory, Step, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot, serialize_match
from rules_engine.combat import _mark_creature_damage, _deal_unblocked_damage, declare_attackers, combat_damage
from rules_engine.continuous import effective_toughness
from rules_engine.engine import RulesEngine
from rules_engine.events import emit_event
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.stack_engine import add_to_stack
from rules_engine.state_based_actions import apply_state_based_actions


@pytest.fixture
def state():
    deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=3)
    state.pregame_pending = False
    state.step = Step.PRECOMBAT_MAIN
    return state


def card(state, cid, name, controller=1, zone=Zone.BATTLEFIELD, types=None, **kwargs):
    obj = CardInstance(id=cid, name=name, owner=controller, controller=controller, zone=zone, types=types or ["Creature"], **kwargs)
    state.cards[cid] = obj
    if zone != Zone.STACK:
        getattr(state.players[controller], zone.value).append(cid)
    return obj


def test_infect_combat_gives_poison_and_ten_counters_lose(state):
    agent = card(state, "infect", "Blighted Agent", power=1, toughness=1, keywords=["infect"])
    assert _deal_unblocked_damage(state, "player:2", 10, agent.id) == 10
    assert state.players[2].life == 20
    assert state.players[2].poison == 10
    apply_state_based_actions(state)
    assert state.winner == 1


def test_noncombat_infect_uses_post_prevention_damage(state):
    card(state, "infect", "Blighted Agent", power=1, toughness=1, keywords=["infect"])
    state.players[2].prevent_damage_shield = 1
    deal_damage(state, 1, {"target_player": 2, "amount": 3, "__source_card_id": "infect"})
    assert state.players[2].poison == 2
    assert state.players[2].life == 20


@pytest.mark.parametrize("keyword", ["infect", "wither"])
def test_counter_damage_can_kill_indestructible_with_zero_toughness(state, keyword):
    card(state, "source", "Blighted Agent", power=1, toughness=1, keywords=[keyword])
    target = card(state, "target", "Darksteel Myr", controller=2, power=0, toughness=1, keywords=["indestructible"])
    _mark_creature_damage(state, target.id, 1, source_id="source")
    assert target.counters["-1/-1"] == 1
    assert "__damage_marked" not in target.counters
    apply_state_based_actions(state)
    assert target.zone == Zone.GRAVEYARD


def test_mixed_infect_and_normal_blockers_keep_damage_sources(state):
    attacker = card(state, "attacker", "Wall of Frost", power=0, toughness=7)
    card(state, "infect", "Blighted Agent", controller=2, power=1, toughness=1, keywords=["infect"])
    card(state, "normal", "Grizzly Bears", controller=2, power=2, toughness=2)
    state.attackers = [attacker.id]
    state.blocks = {attacker.id: ["infect", "normal"]}
    combat_damage(state)
    assert attacker.counters["-1/-1"] == 1
    assert attacker.counters["__damage_marked"] == 2


def test_poison_persists_and_is_exposed(state):
    state.players[1].poison = 4
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.players[1].poison == 4
    assert serialize_match(restored)["players"][1]["poison"] == 4


def test_ninjutsu_is_ability_and_enters_tapped_attacking_same_defender(state):
    attacker = card(state, "attacker", "Grizzly Bears", power=2, toughness=2, summoning_sick=False)
    ninja = card(state, "ninja", "Ninja of the Deep Hours", zone=Zone.HAND, power=2, toughness=2, mana_cost="{3}{U}", oracle_text="Ninjutsu {1}{U}")
    card(state, "prowess", "Monastery Swiftspear", power=1, toughness=2, oracle_text="Prowess")
    state.step = Step.DECLARE_BLOCKERS
    state.blockers_declared = True
    state.attackers = [attacker.id]
    state.attack_targets = {attacker.id: "player:2"}
    state.players[1].mana_pool["U"] = 2
    engine = RulesEngine()
    move = next(move for move in engine.legal_moves(state, 1) if move["type"] == "ninjutsu")
    engine.take_action(state, 1, move)
    assert attacker.zone == Zone.HAND
    assert len(state.stack) == 1
    resolve_top_of_stack(state)
    assert ninja.zone == Zone.BATTLEFIELD and ninja.tapped
    assert ninja.id in state.attackers
    assert state.attack_targets[ninja.id] == "player:2"


def test_ninjutsu_rejects_blocked_attacker_before_paying(state):
    attacker = card(state, "attacker", "Grizzly Bears", power=2, toughness=2)
    ninja = card(state, "ninja", "Ninja of the Deep Hours", zone=Zone.HAND, oracle_text="Ninjutsu {1}{U}")
    state.step = Step.DECLARE_BLOCKERS
    state.blockers_declared = True
    state.attackers = [attacker.id]
    state.blocks = {attacker.id: ["blocker"]}
    state.players[1].mana_pool["U"] = 2
    RulesEngine().take_action(state, 1, {"type": "ninjutsu", "card_id": ninja.id, "return_card_id": attacker.id})
    assert state.players[1].mana_pool["U"] == 2
    assert attacker.zone == Zone.BATTLEFIELD


def test_annihilator_uses_stack_and_defender_choice_survives_snapshot(state):
    attacker = card(state, "crusher", "Ulamog's Crusher", power=8, toughness=8, summoning_sick=False, oracle_text="Annihilator 2 (Whenever this creature attacks, defending player sacrifices two permanents.)")
    card(state, "land-a", "Island", controller=2, types=["Land"])
    card(state, "land-b", "Forest", controller=2, types=["Land"])
    state.step = Step.DECLARE_ATTACKERS
    declare_attackers(state, [attacker.id])
    assert len(state.stack) == 1
    resolve_top_of_stack(state)
    assert state.pending_mechanic_choice["player_id"] == 2
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    engine = RulesEngine()
    engine.take_action(restored, 1, {"type": "choose_mechanic", "card_ids": ["land-a", "land-b"]})
    assert restored.pending_mechanic_choice is not None
    engine.take_action(restored, 2, {"type": "choose_mechanic", "card_ids": ["land-a", "land-a"]})
    assert restored.pending_mechanic_choice is not None
    move = AIAgent().choose_action(restored, engine.legal_moves(restored, 2), 2).action
    engine.take_action(restored, 2, move)
    assert restored.pending_mechanic_choice is None
    assert len(restored.players[2].graveyard) == 2


def test_ai_annihilator_keeps_lands_over_expendable_permanents(state):
    card(state, "land-a", "Island", controller=2, types=["Land"])
    card(state, "land-b", "Forest", controller=2, types=["Land"])
    card(state, "small", "Elvish Mystic", controller=2, types=["Creature"], power=1, toughness=1)
    card(state, "large", "Craw Wurm", controller=2, types=["Creature"], power=6, toughness=4)
    card(state, "token", "Elf Token", controller=2, types=["Creature", "Token"], power=1, toughness=1)
    from rules_engine.keyword_actions import resolve_annihilator

    resolve_annihilator(state, 1, {"target_player": 2, "amount": 2})
    engine = RulesEngine()
    action = AIAgent(archetype="Tribal").choose_action(state, engine.legal_moves(state, 2), 2).action
    assert action["type"] == "choose_mechanic"
    assert action["card_ids"] == ["token", "small"]
    engine.take_action(state, 2, action, reject_invalid=True)
    assert {"land-a", "land-b", "large"} <= set(state.players[2].battlefield)


def test_escape_requires_and_exiles_other_graveyard_cards(state):
    ox = card(state, "ox", "Ox of Agonas", zone=Zone.GRAVEYARD, mana_cost="{3}{R}{R}", power=4, toughness=2, oracle_text="Escape\u2014{R}{R}, Exile eight other cards from your graveyard.\nThis creature escapes with a +1/+1 counter on it.")
    for index in range(8):
        card(state, f"fuel-{index}", "Mountain", zone=Zone.GRAVEYARD, types=["Land"])
    state.players[1].mana_pool["R"] = 2
    engine = RulesEngine()
    move = next(move for move in engine.legal_moves(state, 1) if move["type"] == "cast_spell" and move["card_id"] == ox.id)
    assert move["from_graveyard"]
    engine.take_action(state, 1, move)
    assert len(state.players[1].exile) == 8
    assert ox.id not in state.players[1].exile
    resolve_top_of_stack(state)
    assert ox.zone == Zone.BATTLEFIELD
    assert ox.counters["+1/+1"] == 1


def test_invalid_escape_exile_selection_is_rejected_without_payment(state):
    ox = card(state, "ox", "Ox of Agonas", zone=Zone.GRAVEYARD, mana_cost="{3}{R}{R}", oracle_text="Escape\u2014{R}{R}, Exile eight other cards from your graveyard.")
    for index in range(8):
        card(state, f"fuel-{index}", "Mountain", zone=Zone.GRAVEYARD, types=["Land"])
    state.players[1].mana_pool["R"] = 2
    RulesEngine().take_action(state, 1, {"type": "cast_spell", "card_id": ox.id, "from_graveyard": True, "escape_exile_ids": [ox.id] * 8})
    assert state.players[1].mana_pool["R"] == 2
    assert ox.zone == Zone.GRAVEYARD


def test_prototype_changes_spell_and_permanent_then_restores_on_leaving(state):
    creature = card(state, "prototype", "Phyrexian Fleshgorger", zone=Zone.HAND, types=["Artifact", "Creature"], mana_cost="{7}", power=7, toughness=5, oracle_text="Prototype {1}{B}{B} \u2014 3/3\nMenace, lifelink")
    state.players[1].mana_pool["B"] = 3
    engine = RulesEngine()
    assert any(move["type"] == "cast_spell" and move["card_id"] == creature.id for move in engine.legal_moves(state, 1))
    engine.take_action(state, 1, {"type": "cast_spell", "card_id": creature.id, "cost_choice": {"id": "prototype"}})
    assert (creature.mana_cost, creature.power, creature.toughness) == ("{1}{B}{B}", 3, 3)
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    resolve_top_of_stack(restored)
    assert restored.cards[creature.id].power == 3
    emit_event(restored, "leaves_battlefield", {"card_id": creature.id, "controller": 1})
    assert (restored.cards[creature.id].mana_cost, restored.cards[creature.id].power) == ("{7}", 7)


def test_draw_step_uses_supported_draw_replacement(state):
    card(state, "replacement", "Draw replacement fixture", types=["Enchantment"], oracle_text="If you would draw a card, gain 1 life instead.")
    state.turn = 3
    state.step = Step.UPKEEP
    hand_count = len(state.players[1].hand)
    RulesEngine().next_step(state)
    assert state.players[1].life == 21
    assert len(state.players[1].hand) == hand_count


def test_dredge_is_optional_and_requires_enough_library_cards(state):
    imp = card(state, "imp", "Stinkweed Imp", zone=Zone.GRAVEYARD, power=1, toughness=2, oracle_text="Dredge 5")
    state.turn = 3
    state.step = Step.UPKEEP
    engine = RulesEngine()
    engine.next_step(state)
    assert imp.id in state.pending_mechanic_choice["options"]
    before = len(state.players[1].library)
    engine.take_action(state, 1, {"type": "choose_mechanic", "choice_id": imp.id})
    assert imp.zone == Zone.HAND
    assert len(state.players[1].library) == before - 5
    assert len(state.players[1].graveyard) == 5
    assert state.pending_mechanic_choice is None


def test_dredge_cannot_replace_draw_with_insufficient_library(state):
    imp = card(state, "imp", "Stinkweed Imp", zone=Zone.GRAVEYARD, oracle_text="Dredge 5")
    state.players[1].library = state.players[1].library[:4]
    state.turn = 3
    state.step = Step.UPKEEP
    RulesEngine().next_step(state)
    assert state.pending_mechanic_choice is None
    assert imp.zone == Zone.GRAVEYARD
    assert len(state.players[1].library) == 3


def test_dredge_spell_continuation_survives_snapshot_and_finishes_once(state):
    imp = card(state, "imp", "Stinkweed Imp", zone=Zone.GRAVEYARD, oracle_text="Dredge 5")
    # Deliberately composed effects exercise continuation, not Revitalize's text.
    spell = card(state, "spell", "Revitalize", zone=Zone.STACK, types=["Instant"], mana_cost="{1}{W}")
    add_to_stack(state, spell.id, 1, spell.name, "effect_sequence", {"effects": [
        {"effect_key": "draw_cards", "payload": {"amount": 2}},
        {"effect_key": "gain_life", "payload": {"amount": 3}},
    ]})
    resolve_top_of_stack(state)
    assert spell.zone == Zone.STACK
    assert state.players[1].life == 20
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    engine = RulesEngine()
    engine.take_action(restored, 1, {"type": "choose_mechanic", "choice_id": "draw"})
    assert restored.pending_mechanic_choice is not None
    engine.take_action(restored, 1, {"type": "choose_mechanic", "choice_id": imp.id})
    assert restored.pending_mechanic_choice is None
    assert restored.players[1].life == 23
    assert restored.cards[spell.id].zone == Zone.GRAVEYARD
    assert restored.players[1].graveyard.count(spell.id) == 1


def test_toxic_adds_poison_without_replacing_life_loss(state):
    card(state, "toxic", "Skrelv, Defector Mite", power=1, toughness=1, oracle_text="Toxic 1")
    _deal_unblocked_damage(state, "player:2", 1, "toxic")
    assert (state.players[2].life, state.players[2].poison) == (19, 1)


def test_ninjutsu_remains_available_after_damage_without_second_damage(state):
    attacker = card(state, "attacker", "Ornithopter", power=0, toughness=2)
    ninja = card(state, "ninja", "Ninja of the Deep Hours", zone=Zone.HAND, power=2, toughness=2, oracle_text="Ninjutsu {1}{U}")
    state.players[1].mana_pool["U"] = 2
    state.attackers = [attacker.id]
    state.attack_targets = {attacker.id: "player:2"}
    state.blockers_declared = True
    state.step = Step.COMBAT_DAMAGE
    combat_damage(state)
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    engine = RulesEngine()
    action = next(move for move in engine.legal_moves(restored, 1) if move["type"] == "ninjutsu")
    engine.take_action(restored, 1, action)
    resolve_top_of_stack(restored)
    combat_damage(restored)
    assert restored.players[2].life == 20
    assert ninja.id in restored.attackers
    restored.step = Step.END_COMBAT
    engine.next_step(restored)
    assert restored.attackers == []


def test_nested_draw_sequences_preserve_all_remaining_effects(state):
    card(state, "imp", "Stinkweed Imp", zone=Zone.GRAVEYARD, oracle_text="Dredge 5")
    from effects.registry import resolve_effect
    resolve_effect(state, 1, "effect_sequence", {"effects": [
        {"effect_key": "effect_sequence", "payload": {"effects": [
            {"effect_key": "draw_cards", "payload": {"amount": 2}},
            {"effect_key": "gain_life", "payload": {"amount": 3}},
        ]}},
        {"effect_key": "draw_cards", "payload": {"amount": 1}},
        {"effect_key": "gain_life", "payload": {"amount": 4}},
    ]})
    engine = RulesEngine()
    for _ in range(3):
        assert state.pending_mechanic_choice is not None
        engine.take_action(state, 1, {"type": "choose_mechanic", "choice_id": "draw"})
    assert state.pending_mechanic_choice is None
    assert state.players[1].life == 27


def test_blocked_attacker_without_trample_does_not_hit_player_when_blocker_leaves(state):
    attacker = card(state, "attacker", "Grizzly Bears", power=2, toughness=2)
    blocker = card(state, "blocker", "Ornithopter", controller=2, zone=Zone.GRAVEYARD, power=0, toughness=2)
    state.attackers = [attacker.id]
    state.blocks = {attacker.id: [blocker.id]}
    combat_damage(state)
    assert state.players[2].life == 20


def test_escape_is_available_with_empty_hand(state):
    from rules_engine.costs import collect_cost_options, check_cost_option_available
    state.players[1].hand = []
    ox = card(state, "ox", "Ox of Agonas", zone=Zone.GRAVEYARD, mana_cost="{3}{R}{R}", oracle_text="Escape\u2014{R}{R}, Exile eight other cards from your graveyard.")
    for index in range(8):
        card(state, f"fuel-{index}", "Mountain", zone=Zone.GRAVEYARD, types=["Land"])
    state.players[1].mana_pool["R"] = 2
    option = collect_cost_options(state, 1, ox)[0]
    assert check_cost_option_available(state, 1, ox, option)
