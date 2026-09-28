from __future__ import annotations

from game_state.state import CardInstance, MatchFactory, Step, Zone
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine import combat
from rules_engine.engine import RulesEngine
from rules_engine.move_generator import legal_moves
from rules_engine.stack_engine import resolve_top_of_stack


def game():
    deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=312)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.COMBAT_DAMAGE
    return state


def add_nighthawk(state, card_id: str, controller: int = 1):
    card = CardInstance(
        id=card_id, name="Vampire Nighthawk", owner=controller, controller=controller,
        zone=Zone.BATTLEFIELD, types=["Creature"], power=2, toughness=3,
        keywords=["flying", "deathtouch", "lifelink"],
        oracle_text="Flying, deathtouch, lifelink", summoning_sick=False,
    )
    state.cards[card_id] = card
    state.players[controller].battlefield.append(card_id)
    return card_id


def add_pridemate(state):
    card = CardInstance(
        id="pridemate", name="Ajani's Pridemate", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Creature"], power=2, toughness=2,
        oracle_text="Whenever you gain life, put a +1/+1 counter on Ajani's Pridemate.",
    )
    state.cards[card.id] = card
    state.players[1].battlefield.append(card.id)
    return card.id


def pridemate_triggers(state):
    return [item for item in state.stack if item.source_card_id == "pridemate"]


def test_unblocked_lifelink_emits_life_gain_trigger():
    state = game()
    add_pridemate(state)
    attacker = add_nighthawk(state, "hawk-1")
    state.attackers = [attacker]
    combat.combat_damage(state)
    assert state.players[1].life == 22 and state.players[2].life == 18
    assert len(pridemate_triggers(state)) == 1
    assert resolve_top_of_stack(state)
    assert state.cards["pridemate"].counters.get("+1/+1") == 1


def test_one_lifelink_source_damaging_two_blockers_is_one_gain_event():
    state = game()
    add_pridemate(state)
    attacker = add_nighthawk(state, "hawk-1")
    blockers = []
    for index in (1, 2):
        cid = f"bear-{index}"
        bear = CardInstance(
            id=cid, name="Grizzly Bears", owner=2, controller=2,
            zone=Zone.BATTLEFIELD, types=["Creature"], power=2, toughness=2,
        )
        state.cards[cid] = bear
        state.players[2].battlefield.append(cid)
        blockers.append(cid)
    state.attackers = [attacker]
    state.blocks = {attacker: blockers}
    combat.combat_damage(state)
    assert state.players[1].life == 22
    assert len(pridemate_triggers(state)) == 1


def test_two_lifelink_sources_create_two_gain_events():
    state = game()
    add_pridemate(state)
    state.attackers = [add_nighthawk(state, "hawk-1"), add_nighthawk(state, "hawk-2")]
    combat.combat_damage(state)
    assert state.players[1].life == 24 and state.players[2].life == 16
    assert len(pridemate_triggers(state)) == 2


def test_locked_lifelink_controller_gets_no_gain_event():
    state = game()
    lock = CardInstance(
        id="emperion", name="Platinum Emperion", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Artifact", "Creature"], power=8, toughness=8,
        oracle_text="Your life total can't change.",
    )
    state.cards[lock.id] = lock
    state.players[1].battlefield.append(lock.id)
    add_pridemate(state)
    state.attackers = [add_nighthawk(state, "hawk-1")]
    combat.combat_damage(state)
    assert state.players[1].life == 20 and state.players[2].life == 18
    assert not pridemate_triggers(state)


def test_lifelink_gain_uses_alhammarrets_archive_replacement():
    state = game()
    archive = CardInstance(
        id="archive", name="Alhammarret's Archive", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Artifact"],
        oracle_text="If you would gain life, you gain twice that much life instead.",
    )
    state.cards[archive.id] = archive
    state.players[1].battlefield.append(archive.id)
    state.attackers = [add_nighthawk(state, "hawk-1")]
    combat.combat_damage(state)
    assert state.players[1].life == 24


def test_each_lifelink_source_is_replaced_separately():
    state = game()
    archive = CardInstance(
        id="archive", name="Alhammarret's Archive", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Legendary", "Artifact"],
        oracle_text="If you would gain life, you gain twice that much life instead.",
    )
    state.cards[archive.id] = archive
    state.players[1].battlefield.append(archive.id)
    add_pridemate(state)
    state.attackers = [add_nighthawk(state, "hawk-1"), add_nighthawk(state, "hawk-2")]
    combat.combat_damage(state)
    assert state.players[1].life == 28
    assert len(pridemate_triggers(state)) == 2


def test_human_lifelink_replacement_choice_survives_snapshot_before_sba():
    state = game()
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    for cid, name, types in (
        ("archive", "Alhammarret's Archive", ["Legendary", "Artifact"]),
        ("reflection", "Boon Reflection", ["Enchantment"]),
    ):
        card = CardInstance(
            id=cid, name=name, owner=1, controller=1,
            zone=Zone.BATTLEFIELD, types=types,
            oracle_text="If you would gain life, you gain twice that much life instead.",
        )
        state.cards[cid] = card
        state.players[1].battlefield.append(cid)
    add_pridemate(state)
    state.attackers = [add_nighthawk(state, "hawk-1")]
    combat.combat_damage(state)
    assert state.players[1].life == 20
    assert state.players[2].life == 18
    assert state.trigger_staging
    assert not pridemate_triggers(state)
    assert {move["replacement_source_id"] for move in legal_moves(state, 1)} == {"archive", "reflection"}

    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    RulesEngine().take_action(state, 1, {"type": "choose_replacement", "replacement_source_id": "reflection"})
    assert state.players[1].life == 28
    assert not state.pending_replacement_choice
    assert not state.trigger_staging
    assert len(pridemate_triggers(state)) == 1


def test_lifelink_source_death_waits_for_gain_choice():
    state = game()
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    for cid, name, types in (
        ("archive", "Alhammarret's Archive", ["Legendary", "Artifact"]),
        ("reflection", "Boon Reflection", ["Enchantment"]),
    ):
        card = CardInstance(
            id=cid, name=name, owner=1, controller=1,
            zone=Zone.BATTLEFIELD, types=types,
            oracle_text="If you would gain life, you gain twice that much life instead.",
        )
        state.cards[cid] = card
        state.players[1].battlefield.append(cid)
    attacker = add_nighthawk(state, "hawk-1")
    blocker = CardInstance(
        id="blocker", name="Centaur Courser", owner=2, controller=2,
        zone=Zone.BATTLEFIELD, types=["Creature"], power=3, toughness=3,
    )
    state.cards[blocker.id] = blocker
    state.players[2].battlefield.append(blocker.id)
    state.attackers = [attacker]
    state.blocks = {attacker: [blocker.id]}
    combat.combat_damage(state)
    assert state.cards[attacker].zone == Zone.BATTLEFIELD
    assert state.pending_replacement_choice
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    RulesEngine().take_action(state, 1, {"type": "choose_replacement", "replacement_source_id": "archive"})
    assert state.players[1].life == 28
    assert state.cards[attacker].zone == Zone.GRAVEYARD
    assert not state.trigger_staging


def test_separate_lifelink_sources_resume_both_human_choices():
    state = game()
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    for cid, name, types in (
        ("archive", "Alhammarret's Archive", ["Legendary", "Artifact"]),
        ("reflection", "Boon Reflection", ["Enchantment"]),
    ):
        card = CardInstance(
            id=cid, name=name, owner=1, controller=1,
            zone=Zone.BATTLEFIELD, types=types,
            oracle_text="If you would gain life, you gain twice that much life instead.",
        )
        state.cards[cid] = card
        state.players[1].battlefield.append(cid)
    add_pridemate(state)
    state.attackers = [add_nighthawk(state, "hawk-1"), add_nighthawk(state, "hawk-2")]
    combat.combat_damage(state)
    assert state.pending_replacement_choice
    assert state.players[1].life == 20

    engine = RulesEngine()
    engine.take_action(state, 1, {"type": "choose_replacement", "replacement_source_id": "archive"})
    assert state.players[1].life == 28
    assert state.pending_replacement_choice
    assert state.trigger_staging
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    engine.take_action(state, 1, {"type": "choose_replacement", "replacement_source_id": "reflection"})
    assert state.players[1].life == 36
    assert len(pridemate_triggers(state)) == 2
    assert not state.trigger_staging
