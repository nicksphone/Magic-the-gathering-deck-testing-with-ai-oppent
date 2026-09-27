"""Cast triggers choose ability targets after spell announcement."""
from game_state.state import Zone
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_permanent_spell_context import card, state


def _cast_ulamog():
    game = state()
    game.trigger_order_choice_required = True
    game.trigger_order_choice_players = {1}
    ring = card(game, "Sol Ring", Zone.BATTLEFIELD, owner=1)
    copter = card(game, "Smuggler's Copter", Zone.BATTLEFIELD, owner=2)
    ulamog = card(game, "Ulamog, the Infinite Gyre")
    rules = RulesEngine()
    game = checked_action(game, rules, 1, {"type": "cast_spell", "card_id": ulamog.id})
    return game, rules, ring.id, copter.id, ulamog.id


def test_cast_trigger_target_is_chosen_after_spell_and_resolves_first():
    game, rules, ring, copter, ulamog = _cast_ulamog()
    assert game.cards[ulamog].zone == Zone.STACK
    assert len(game.stack) == 2
    assert game.stack[0].source_card_id == ulamog
    assert game.stack[1].payload["__trigger_event"] == "spell_cast"
    assert game.pending_trigger_order["phase"] == "targets"
    assert {move["target_card_id"] for move in rules.legal_moves(game, 1)} == {ring, copter}
    game = deserialize_match_snapshot(serialize_match_snapshot(game))
    choice = next(move for move in rules.legal_moves(game, 1) if move["target_card_id"] == ring)
    game = checked_action(game, rules, 1, {
        "type": "choose_trigger_target", "stack_id": choice["stack_id"], "target_card_id": ring,
    })
    resolve_top_of_stack(game)
    assert game.cards[ring].zone == Zone.GRAVEYARD
    assert game.cards[copter].zone == Zone.BATTLEFIELD
    assert game.cards[ulamog].zone == Zone.STACK
    resolve_top_of_stack(game)
    assert game.cards[ulamog].zone == Zone.BATTLEFIELD


def test_cast_trigger_survives_countering_source_spell():
    game, rules, ring, copter, ulamog = _cast_ulamog()
    choice = next(move for move in rules.legal_moves(game, 1) if move["target_card_id"] == copter)
    game = checked_action(game, rules, 1, {
        "type": "choose_trigger_target", "stack_id": choice["stack_id"], "target_card_id": copter,
    })
    from effects.handlers import counter_spell
    counter_spell(game, 2, {"target_stack_id": game.stack[0].id})
    assert game.cards[ulamog].zone == Zone.GRAVEYARD
    resolve_top_of_stack(game)
    assert game.cards[copter].zone == Zone.GRAVEYARD
    assert game.cards[ring].zone == Zone.BATTLEFIELD


def test_copying_spell_does_not_retrigger_its_cast_only_ability():
    game, rules, ring, _, ulamog = _cast_ulamog()
    choice = next(move for move in rules.legal_moves(game, 1) if move["target_card_id"] == ring)
    game = checked_action(game, rules, 1, {
        "type": "choose_trigger_target", "stack_id": choice["stack_id"], "target_card_id": ring,
    })
    from rules_engine.events import emit_event
    emit_event(game, "spell_copy", {"source_card_id": ulamog, "controller": 1})
    assert len(game.stack) == 2


def test_copy_does_not_trigger_prowess_but_cast_does():
    game = state()
    card(game, "Monastery Swiftspear", Zone.BATTLEFIELD)
    bolt = card(game, "Lightning Bolt")
    game.players[1].hand.remove(bolt.id)
    bolt.zone = Zone.STACK
    from rules_engine.events import emit_event
    emit_event(game, "spell_copy", {"source_card_id": bolt.id, "controller": 1})
    assert not game.stack
    emit_event(game, "spell_cast", {"source_card_id": bolt.id, "controller": 1})
    assert len(game.stack) == 1
    assert game.stack[0].effect_key == "temporary_pt_buff"


def test_cast_spell_still_exists_when_cast_trigger_has_no_legal_target():
    game = state()
    game.trigger_order_choice_required = True
    game.trigger_order_choice_players = {1}
    ulamog = card(game, "Ulamog, the Infinite Gyre")
    game = checked_action(game, RulesEngine(), 1, {"type": "cast_spell", "card_id": ulamog.id})
    assert game.cards[ulamog.id].zone == Zone.STACK
    assert len(game.stack) == 1
    assert game.pending_trigger_order is None
