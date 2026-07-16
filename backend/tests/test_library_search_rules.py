from effects.registry import resolve_effect
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.ability_model import build_ability_spec


def _state_with_searcher() -> object:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck, seed=11)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    for cid in state.players[1].library:
        state.cards[cid].types = ["Land"]
        state.cards[cid].type_line = "Basic Land — Forest"
    return state


def test_cultivate_inference_searches_up_to_two_basic_lands_to_hand() -> None:
    state = _state_with_searcher()
    spell = CardInstance(
        id="cultivate",
        name="Cultivate",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        oracle_text="Search your library for up to two basic land cards, reveal those cards, put them into your hand, then shuffle.",
    )
    state.cards[spell.id] = spell
    spec = build_ability_spec(state, spell, 1)

    assert spec.effect.key == "search_library"
    assert spec.effect.payload == {
        "contains": "basic_land",
        "destination": "hand",
        "count": 2,
        "shuffle": True,
    }
    before = len(state.players[1].hand)
    resolve_effect(state, 1, spec.effect.key, spec.effect.payload)
    assert len(state.players[1].hand) == before + 2
    assert all("Basic" in state.cards[cid].type_line for cid in state.players[1].hand[-2:])
    assert any("shuffles their library" in line.lower() for line in state.log)


def test_migration_path_puts_basic_lands_onto_battlefield_tapped() -> None:
    state = _state_with_searcher()
    spell = CardInstance(
        id="migration-path",
        name="Migration Path",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        oracle_text="Search your library for up to two basic land cards, put them onto the battlefield tapped, then shuffle.",
    )
    state.cards[spell.id] = spell
    spec = build_ability_spec(state, spell, 1)
    resolve_effect(state, 1, spec.effect.key, spec.effect.payload)

    found = [cid for cid in state.players[1].battlefield if cid != spell.id]
    assert len(found) == 2
    assert all(state.cards[cid].tapped for cid in found)
