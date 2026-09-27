"""Canonical transforming faces must keep numeric state safe for combat and AI."""
from ai.agent import AIAgent
from effects.handlers import transform_card, transform_if_top_matches
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.continuous import effective_power, effective_toughness


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
    saga = CardInstance(
        id="kumano", name="Kumano Faces Kakkazan", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Enchantment"], mana_cost="{R}",
        type_line="Enchantment \u2014 Saga", layout="transform",
        card_faces=[
            {"name": "Kumano Faces Kakkazan", "mana_cost": "{R}", "type_line": "Enchantment \u2014 Saga",
             "oracle_text": "III \u2014 Exile this Saga, then return it to the battlefield transformed under your control."},
            {"name": "Etching of Kumano", "mana_cost": "", "type_line": "Enchantment Creature \u2014 Human Shaman",
             "oracle_text": "Haste\nIf a creature dealt damage this turn by a source you controlled would die, exile it instead.",
             "power": "2", "toughness": "2"},
        ],
    )
    game.cards[saga.id] = saga
    game.players[1].battlefield.append(saga.id)
    transform_card(game, 1, {"target_card_id": saga.id, "face_index": 1})
    assert (saga.power, saga.toughness) == (2, 2)
    assert (effective_power(game, saga.id), effective_toughness(game, saga.id)) == (2, 2)
    assert AIAgent()._forced_sweeper_stabilization_line(game, [{"type": "pass_priority"}], 2) is None


def test_revealed_instant_transforms_delver_to_numeric_flying_face():
    game = _game()
    delver = CardInstance(
        id="delver", name="Delver of Secrets", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Creature"], mana_cost="{U}",
        type_line="Creature \u2014 Human Wizard", power=1, toughness=1, layout="transform",
        card_faces=[
            {"name": "Delver of Secrets", "mana_cost": "{U}", "type_line": "Creature \u2014 Human Wizard",
             "oracle_text": "At the beginning of your upkeep, look at the top card of your library. You may reveal that card. If an instant or sorcery card is revealed this way, transform this creature.",
             "power": "1", "toughness": "1"},
            {"name": "Insectile Aberration", "mana_cost": "", "type_line": "Creature \u2014 Human Insect",
             "oracle_text": "Flying", "power": "3", "toughness": "2"},
        ],
    )
    game.cards[delver.id] = delver
    game.players[1].battlefield.append(delver.id)
    top_id = game.players[1].library[-1]
    game.cards[top_id].name = "Lightning Bolt"
    game.cards[top_id].types = ["Instant"]
    transform_if_top_matches(game, 1, {"target_card_id": delver.id, "required_types": ["Instant"], "face_index": 1})
    assert (delver.power, delver.toughness) == (3, 2)
    assert delver.keywords == ["flying"]
