"""Actual canonical Oracle fixtures; never loaded into the playable cache."""
import json
from pathlib import Path

from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack

DATA = json.loads((Path(__file__).parent / "fixtures/permanent_spell_context.json").read_text())


def state():
    game = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}], seed=61)
    game.pregame_pending = False
    game.kept_hands = {1, 2}
    game.step = Step.PRECOMBAT_MAIN
    game.players[1].mana_pool.update({color: 20 for color in "WUBRGC"})
    return game


def card(game, name, zone=Zone.HAND, owner=1):
    row = DATA[name]
    obj = CardInstance(id=name, name=name, owner=owner, controller=owner, zone=zone,
                       types=row["type_line"].split(" — ")[0].split(), type_line=row["type_line"],
                       oracle_text=row["oracle_text"], mana_cost=row["mana_cost"],
                       power=int(row["power"]) if row["power"] is not None else None,
                       toughness=int(row["toughness"]) if row["toughness"] is not None else None)
    game.cards[obj.id] = obj
    getattr(game.players[owner], zone.value).append(obj.id)
    return obj


def cast(game, obj, targets=None):
    RulesEngine().take_action(game, 1, {"type": "cast_spell", "card_id": obj.id, "targets": targets or {}}, reject_invalid=True)
    assert obj.zone == Zone.STACK


def test_activated_damage_does_not_happen_when_creature_spell_resolves():
    game = state()
    pyro = card(game, "Prodigal Pyromancer")
    cast(game, pyro)
    assert game.stack[-1].effect_key == "noop"
    resolve_top_of_stack(game)
    assert pyro.zone == Zone.BATTLEFIELD
    assert game.players[2].life == 20
    assert not game.stack


def test_etb_draw_waits_for_its_separate_trigger_and_occurs_once():
    game = state()
    wall = card(game, "Wall of Omens")
    cast(game, wall)
    before = len(game.players[1].hand)
    resolve_top_of_stack(game)
    assert wall.zone == Zone.BATTLEFIELD
    assert len(game.players[1].hand) == before
    assert len(game.stack) == 1
    assert game.stack[0].payload["__trigger_event"] == "enters_battlefield"
    resolve_top_of_stack(game)
    assert len(game.players[1].hand) == before + 1
    assert not game.stack


def test_modern_another_enters_trigger_is_not_a_self_entry_or_cast_effect():
    game = state()
    warden = card(game, "Soul Warden")
    cast(game, warden)
    resolve_top_of_stack(game)
    assert game.players[1].life == 20
    assert not game.stack
    wall = card(game, "Wall of Omens")
    cast(game, wall)
    resolve_top_of_stack(game)
    assert len(game.stack) == 2
    assert game.players[1].life == 20
    while game.stack:
        resolve_top_of_stack(game)
    assert game.players[1].life == 21


def test_aura_attaches_without_executing_its_later_draw_ability():
    game = state()
    pyro = card(game, "Prodigal Pyromancer", Zone.BATTLEFIELD)
    aura = card(game, "Curiosity")
    cast(game, aura, {"target_card_id": pyro.id})
    before = len(game.players[1].hand)
    resolve_top_of_stack(game)
    assert aura.attached_to == pyro.id
    assert len(game.players[1].hand) == before
    assert not game.stack


def test_targeted_etb_does_not_destroy_before_the_creature_enters():
    game = state()
    target = card(game, "Smuggler's Copter", Zone.BATTLEFIELD, owner=2)
    sage = card(game, "Reclamation Sage")
    cast(game, sage)
    resolve_top_of_stack(game)
    assert sage.zone == Zone.BATTLEFIELD
    assert target.zone == Zone.BATTLEFIELD
    assert len(game.stack) == 1
    resolve_top_of_stack(game)
    assert target.zone == Zone.GRAVEYARD
    assert not game.stack
