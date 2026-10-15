"""Canonical transforming faces must keep numeric state safe for combat and AI."""
from dataclasses import replace

from ai.agent import AIAgent
from effects.handlers import transform_card, transform_if_top_matches
from game_state.state import MatchFactory, Step, Zone
from rules_engine.continuous import effective_power, effective_toughness
from tests.canonical_positive_fixtures import raw_card


def _canonical_instance(name, card_id, zone, *, owner=1, controller=1, instance_order=0):
    raw = raw_card(name)
    # Eight copies leave one never-drawn template after the real opening draw.
    materialized = MatchFactory.from_decks(
        [{**raw, "card_name": raw["name"], "quantity": 8}], [], seed=77)
    template = next(card for card in materialized.cards.values() if card.zone == Zone.LIBRARY)
    return replace(template, id=card_id, owner=owner, controller=controller,
                   zone=zone, instance_order=instance_order,
                   summoning_sick=True if zone == Zone.BATTLEFIELD else template.summoning_sick)


def _game():
    game = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Island"}],
        [{"quantity": 60, "card_name": "Island"}], seed=77,
    )
    game.pregame_pending = False
    game.step = Step.PRECOMBAT_MAIN
    game.active_player = game.priority_player = 2
    return game


def test_kumano_transforms_to_numeric_creature_and_ai_can_assess_it():
    game = _game()
    saga = _canonical_instance("Kumano Faces Kakkazan // Etching of Kumano", "kumano", Zone.BATTLEFIELD)
    game.cards[saga.id] = saga
    game.players[1].battlefield.append(saga.id)
    transform_card(game, 1, {"target_card_id": saga.id, "face_index": 1})
    assert (saga.power, saga.toughness) == (2, 2)
    assert (effective_power(game, saga.id), effective_toughness(game, saga.id)) == (2, 2)
    assert AIAgent()._forced_sweeper_stabilization_line(game, [{"type": "pass_priority"}], 2) is None


def test_revealed_instant_transforms_delver_to_numeric_flying_face():
    game = _game()
    delver = _canonical_instance("Delver of Secrets // Insectile Aberration", "delver", Zone.BATTLEFIELD)
    game.cards[delver.id] = delver
    game.players[1].battlefield.append(delver.id)
    top_id = game.players[1].library[-1]
    top = game.cards[top_id]
    game.cards[top_id] = _canonical_instance(
        "Lightning Bolt", top_id, top.zone, owner=top.owner,
        controller=top.controller, instance_order=top.instance_order)
    transform_if_top_matches(game, 1, {"target_card_id": delver.id, "required_types": ["Instant"], "face_index": 1})
    assert (delver.power, delver.toughness) == (3, 2)
    assert delver.keywords == ["flying"]
