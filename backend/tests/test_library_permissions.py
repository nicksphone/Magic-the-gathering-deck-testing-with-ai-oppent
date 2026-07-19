from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine.library_permissions import top_library_creature_for_type
from rules_engine.move_generator import legal_moves


def _base_state():
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Island"}],
        [{"quantity": 60, "card_name": "Island"}],
        seed=61,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    land = state.players[1].library.pop()
    state.players[1].battlefield.append(land)
    state.cards[land].zone = Zone.BATTLEFIELD
    state.cards[land].summoning_sick = False
    return state


def test_realmwalker_exposes_only_matching_top_creature_as_library_cast() -> None:
    state = _base_state()
    walker = CardInstance(
        id="walker",
        name="Realmwalker",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        type_line="Creature — Elf Shaman",
        chosen_creature_type="Elf",
        oracle_text=(
            "Changeling As this creature enters, choose a creature type. You may look at "
            "the top card of your library any time. You may cast creature spells of the "
            "chosen type from the top of your library."
        ),
    )
    top = CardInstance(
        id="top-elf",
        name="Llanowar Elves",
        owner=1,
        controller=1,
        zone=Zone.LIBRARY,
        types=["Creature"],
        type_line="Creature — Elf Druid",
        mana_cost="{U}",
    )
    state.cards.update({walker.id: walker, top.id: top})
    state.players[1].battlefield.append(walker.id)
    state.players[1].library.append(top.id)

    assert top_library_creature_for_type(state, 1) is top
    move = next(item for item in legal_moves(state, 1) if item.get("from_library"))
    RulesEngine().take_action(
        state,
        1,
        {"type": "cast_spell", "card_id": top.id, "from_library": True},
    )

    assert top.id not in state.players[1].library
    assert state.stack and state.stack[-1].source_card_id == top.id
    assert move["card_id"] == top.id


def test_realmwalker_choice_is_persisted_when_it_enters() -> None:
    state = _base_state()
    walker = CardInstance(
        id="walker-choice",
        name="Realmwalker",
        owner=1,
        controller=1,
        zone=Zone.STACK,
        types=["Creature"],
        type_line="Creature — Elf Shaman",
        oracle_text=(
            "Changeling As this creature enters, choose a creature type. You may look at "
            "the top card of your library any time. You may cast creature spells of the "
            "chosen type from the top of your library."
        ),
    )
    state.cards[walker.id] = walker
    state.stack.append(
        type(
            "Stack",
            (),
            {
                "id": "walker-stack",
                "source_card_id": walker.id,
                "controller": 1,
                "label": walker.name,
                "effect_key": "noop",
                "payload": {"chosen_creature_type": "Elf"},
            },
        )()
    )

    from rules_engine.stack_engine import resolve_top_of_stack

    resolve_top_of_stack(state)

    assert walker.chosen_creature_type == "elf"
