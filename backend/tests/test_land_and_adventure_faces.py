"""Canonical land/Adventure lifecycle fixtures, without cache or network writes."""
import pytest

from tests.test_modal_spell_faces import fixture
from game_state.state import CardInstance, Step, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import validate_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.state_based_actions import apply_state_based_actions

RECOVERY = "Bala Ged Recovery // Bala Ged Sanctuary"
PATHWAY = "Riverglide Pathway // Lavaglide Pathway"
GIANT = "Bonecrusher Giant // Stomp"
BORROWER = "Brazen Borrower // Petty Theft"


def test_modal_land_is_played_tapped_without_cast_or_mana_payment():
    game, card = fixture(RECOVERY)
    rules = RulesEngine()
    before_mana = dict(game.players[1].mana_pool)
    action = {"type": "play_land", "card_id": card.id, "selected_face_index": 1}
    validate_action(game, rules, 1, action)
    rules.take_action(game, 1, action, reject_invalid=True)
    assert card.name == "Bala Ged Sanctuary"
    assert card.zone == Zone.BATTLEFIELD and card.types == ["Land"] and card.tapped
    assert game.players[1].mana_pool == before_mana and not game.stack
    assert game.players[1].lands_played_this_turn == 1
    restored = deserialize_match_snapshot(serialize_match_snapshot(game))
    assert restored.cards[card.id].name == "Bala Ged Sanctuary"
    assert not any(move["type"] == "play_land" for move in rules.legal_moves(restored, 1))


def test_both_pathway_faces_are_land_choices_with_correct_mana():
    game, card = fixture(PATHWAY)
    rules = RulesEngine()
    faces = {move.get("selected_face_index", 0) for move in rules.legal_moves(game, 1) if move["type"] == "play_land" and move["card_id"] == card.id}
    assert faces == {0, 1}
    rules.take_action(game, 1, {"type": "play_land", "card_id": card.id, "selected_face_index": 1}, reject_invalid=True)
    assert card.name == "Lavaglide Pathway" and not card.tapped
    before = game.players[1].mana_pool["R"]
    rules.take_action(game, 1, {"type": "tap_land_for_mana", "card_id": card.id, "color": "R"}, reject_invalid=True)
    assert game.players[1].mana_pool["R"] == before + 1


def test_exile_land_face_needs_unexpired_permission():
    game, card = fixture(RECOVERY)
    game.players[1].hand.remove(card.id)
    game.players[1].exile.append(card.id)
    card.zone = Zone.EXILE
    rules = RulesEngine()
    action = {"type": "play_land", "card_id": card.id, "selected_face_index": 1, "from_exile": True}
    with pytest.raises(ActionRejected):
        validate_action(game, rules, 1, action)
    game.players[1].exile_play_until[card.id] = game.turn
    validate_action(game, rules, 1, action)
    rules.take_action(game, 1, action, reject_invalid=True)
    assert card.id not in game.players[1].exile_play_until
    assert card.zone == Zone.BATTLEFIELD


def stomp(game, card, target=None):
    action = {"type": "cast_spell", "card_id": card.id, "selected_face_index": 1,
              "targets": {"target_card_id": target} if target else {"target_player": 2}}
    rules = RulesEngine()
    validate_action(game, rules, 1, action)
    rules.take_action(game, 1, action, reject_invalid=True)
    return rules


def test_adventure_resolves_then_normal_face_is_castable_after_snapshot_and_later_turn():
    game, card = fixture(GIANT)
    rules = stomp(game, card)
    assert card.name == "Stomp" and card.types == ["Instant"]
    resolve_top_of_stack(game)
    assert game.players[2].life == 18
    assert card.zone == Zone.EXILE and game.adventure_permissions[card.id] == 1
    assert card.types == ["Creature"] and card.mana_cost == "{2}{R}"
    game = deserialize_match_snapshot(serialize_match_snapshot(game))
    game.turn += 4
    game.priority_player = 1
    moves = [move for move in rules.legal_moves(game, 1) if move.get("card_id") == card.id and move["type"] == "cast_spell"]
    assert moves and all(move.get("selected_face_index", 0) == 0 for move in moves)
    action = {"type": "cast_spell", "card_id": card.id, "from_exile": True}
    validate_action(game, rules, 1, action)
    rules.take_action(game, 1, action, reject_invalid=True)
    assert card.id not in game.adventure_permissions
    resolve_top_of_stack(game)
    assert game.cards[card.id].zone == Zone.BATTLEFIELD


def test_countered_adventure_does_not_grant_exile_permission():
    from effects.handlers import counter_spell
    game, card = fixture(GIANT)
    stomp(game, card)
    counter_spell(game, 2, {"target_stack_id": game.stack[-1].id})
    apply_state_based_actions(game)
    assert card.zone == Zone.GRAVEYARD and card.types == ["Creature"]
    assert card.id not in game.adventure_permissions and card.id not in game.players[1].exile


def test_adventure_with_a_missing_target_does_not_resolve_or_grant_permission():
    game, card = fixture(GIANT)
    bear = CardInstance(id="bear", name="Grizzly Bears", owner=2, controller=2, zone=Zone.BATTLEFIELD, types=["Creature"], power=2, toughness=2)
    game.cards[bear.id] = bear
    game.players[2].battlefield.append(bear.id)
    stomp(game, card, bear.id)
    game.players[2].battlefield.remove(bear.id)
    game.players[2].graveyard.append(bear.id)
    bear.zone = Zone.GRAVEYARD
    resolve_top_of_stack(game)
    assert card.zone == Zone.GRAVEYARD and card.id not in game.adventure_permissions
    assert any("does not resolve" in line for line in game.log)


def test_flash_adventure_primary_can_be_cast_on_opponents_turn_but_stomp_cannot_repeat():
    game, card = fixture(GIANT)
    rules = stomp(game, card)
    resolve_top_of_stack(game)
    with pytest.raises(ActionRejected):
        validate_action(game, rules, 1, {"type": "cast_spell", "card_id": card.id, "from_exile": True, "selected_face_index": 1, "targets": {"target_player": 2}})
    other, borrower = fixture(BORROWER)
    other.players[1].hand.remove(borrower.id)
    other.players[1].exile.append(borrower.id)
    borrower.zone = Zone.EXILE
    other.adventure_permissions[borrower.id] = 1
    other.active_player = 2
    other.step = Step.UPKEEP
    validate_action(other, rules, 1, {"type": "cast_spell", "card_id": borrower.id, "from_exile": True})


def test_adventure_permission_belongs_to_caster_not_owner():
    game, card = fixture(GIANT)
    card.owner = 2
    rules = stomp(game, card)
    resolve_top_of_stack(game)
    assert card.id in game.players[2].exile and game.adventure_permissions[card.id] == 1
    assert any(move.get("card_id") == card.id for move in rules.legal_moves(game, 1))
    rules.take_action(game, 1, {"type": "cast_spell", "card_id": card.id, "from_exile": True}, reject_invalid=True)
    resolve_top_of_stack(game)
    assert card.id in game.players[1].battlefield and card.id not in game.players[2].battlefield


def test_generic_exile_does_not_allow_casting_an_adventurer():
    game, card = fixture(GIANT)
    game.players[1].hand.remove(card.id)
    game.players[1].exile.append(card.id)
    card.zone = Zone.EXILE
    assert not any(move.get("card_id") == card.id for move in RulesEngine().legal_moves(game, 1))


def test_permission_is_consumed_and_not_reused_after_reexiling_the_permanent():
    game, card = fixture(GIANT)
    rules = stomp(game, card)
    resolve_top_of_stack(game)
    rules.take_action(game, 1, {"type": "cast_spell", "card_id": card.id, "from_exile": True}, reject_invalid=True)
    resolve_top_of_stack(game)
    game.players[1].battlefield.remove(card.id)
    game.players[1].exile.append(card.id)
    card.zone = Zone.EXILE
    assert card.id not in game.adventure_permissions
    assert not any(move.get("card_id") == card.id for move in rules.legal_moves(game, 1))


def test_ai_materializes_the_available_adventure_face_and_target():
    from ai.agent import AIAgent
    game, card = fixture(GIANT)
    rules = RulesEngine()
    move = next(move for move in rules.legal_moves(game, 1)
                if move.get("card_id") == card.id and move.get("selected_face_index") == 1)
    action = AIAgent(difficulty="master", archetype="Burn")._materialize_action(game, move, 1)
    assert action["selected_face_index"] == 1
    assert action["targets"]["target_player"] == 2
    rules.take_action(game, 1, action, reject_invalid=True)
    assert card.name == "Stomp" and card.zone == Zone.STACK
