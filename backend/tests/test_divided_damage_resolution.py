"""Resolution-time target legality for a real divided-damage spell."""
from game_state.state import CardInstance, Zone
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_permanent_spell_context import state


def _setup():
    game = state()
    spell = CardInstance(
        id="pyrotechnics", name="Pyrotechnics", owner=1, controller=1,
        zone=Zone.HAND, types=["Sorcery"], mana_cost="{4}{R}",
        oracle_text="Pyrotechnics deals 4 damage divided as you choose among any number of targets.",
    )
    game.cards[spell.id] = spell
    game.players[1].hand.append(spell.id)
    for cid in ("first", "second"):
        wall = CardInstance(
            id=cid, name="Wall of Omens", owner=2, controller=2,
            zone=Zone.BATTLEFIELD, types=["Creature"],
            mana_cost="{1}{W}", power=0, toughness=4,
            oracle_text="Defender\nWhen this creature enters, draw a card.",
        )
        game.cards[cid] = wall
        game.players[2].battlefield.append(cid)
    return game


def _cast(game):
    return checked_action(game, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": "pyrotechnics",
        "targets": {"target_distribution": {"first": 2, "second": 2}},
    })


def test_divided_damage_requires_a_recipient_when_players_have_shroud():
    game = _setup()
    for cid in ("first", "second"):
        game.players[2].battlefield.remove(cid)
        game.cards[cid].zone = Zone.GRAVEYARD
        game.players[2].graveyard.append(cid)
    for player_id in (1, 2):
        shield = CardInstance(
            id=f"mask-{player_id}", name="Ivory Mask", owner=player_id, controller=player_id,
            zone=Zone.BATTLEFIELD, types=["Enchantment"], oracle_text="You have shroud.",
        )
        game.cards[shield.id] = shield
        game.players[player_id].battlefield.append(shield.id)
    assert not any(
        move.get("type") == "cast_spell" and move.get("card_id") == "pyrotechnics"
        for move in RulesEngine().legal_moves(game, 1)
    )


def test_one_illegal_target_keeps_original_damage_split():
    game = _cast(_setup())
    game.players[2].battlefield.remove("first")
    game.players[2].graveyard.append("first")
    game.cards["first"].zone = Zone.GRAVEYARD
    resolve_top_of_stack(game)
    assert game.cards["first"].counters.get("__damage_marked", 0) == 0
    assert game.cards["second"].counters.get("__damage_marked", 0) == 2
    assert game.cards["pyrotechnics"].zone == Zone.GRAVEYARD


def test_all_illegal_targets_prevent_spell_from_resolving():
    game = _cast(_setup())
    for cid in ("first", "second"):
        game.players[2].battlefield.remove(cid)
        game.players[2].graveyard.append(cid)
        game.cards[cid].zone = Zone.GRAVEYARD
    resolve_top_of_stack(game)
    assert all(game.cards[cid].counters.get("__damage_marked", 0) == 0 for cid in ("first", "second"))
    assert game.cards["pyrotechnics"].zone == Zone.GRAVEYARD
    assert "does not resolve" in game.log[-1]


def test_protection_makes_divided_target_illegal_at_cast_and_resolution():
    game = _setup()
    game.cards["first"].keywords.append("protection from red")
    try:
        _cast(game)
    except ActionRejected:
        pass
    else:
        raise AssertionError("Protected target must be rejected at announcement")
    game.cards["first"].keywords.clear()
    game = _cast(game)
    game.cards["first"].keywords.append("protection from red")
    resolve_top_of_stack(game)
    assert game.cards["first"].counters.get("__damage_marked", 0) == 0
    assert game.cards["second"].counters.get("__damage_marked", 0) == 2


def test_hexproof_after_cast_does_not_redirect_damage_after_snapshot():
    game = _cast(_setup())
    game = deserialize_match_snapshot(serialize_match_snapshot(game))
    game.cards["first"].keywords.append("hexproof")
    resolve_top_of_stack(game)
    assert game.cards["first"].counters.get("__damage_marked", 0) == 0
    assert game.cards["second"].counters.get("__damage_marked", 0) == 2


def test_player_recipient_still_gets_announced_share_when_card_target_leaves():
    game = _setup()
    game = checked_action(game, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": "pyrotechnics",
        "targets": {"target_distribution": {"first": 1, "2": 3}},
    })
    game.players[2].battlefield.remove("first")
    game.players[2].graveyard.append("first")
    game.cards["first"].zone = Zone.GRAVEYARD
    resolve_top_of_stack(game)
    assert game.players[2].life == 17
    assert game.cards["first"].counters.get("__damage_marked", 0) == 0
