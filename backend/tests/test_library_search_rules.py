from effects.registry import resolve_effect
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.ability_model import build_ability_spec
from rules_engine.cast_choice import build_cast_hints, validate_cast_choice


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


def test_library_search_exposes_candidates_and_honors_explicit_selection() -> None:
    state = _state_with_searcher()
    state.players[1].library[-1], state.players[1].library[-2] = (
        state.players[1].library[-2],
        state.players[1].library[-1],
    )
    spell = CardInstance(
        id="cultivate-choice",
        name="Cultivate",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        oracle_text="Search your library for up to two basic land cards, reveal those cards, put them into your hand, then shuffle.",
    )
    state.cards[spell.id] = spell
    hints = build_cast_hints(state, spell, 1)
    candidates = hints["library_search"]["candidates"]
    assert len(candidates) == len(state.players[1].library)
    chosen = [candidates[-1]["id"]]
    ok, error = validate_cast_choice(hints, {"search_card_ids": chosen})
    assert ok is True, error

    spec = build_ability_spec(state, spell, 1, action_targets={"search_card_ids": chosen})
    assert spec.effect.payload["selected_card_ids"] == chosen
    resolve_effect(state, 1, spec.effect.key, spec.effect.payload)
    assert chosen[0] in state.players[1].hand
    assert state.cards[chosen[0]].type_line.startswith("Basic Land")


def test_library_search_rejects_nonmatching_explicit_selection() -> None:
    state = _state_with_searcher()
    nonbasic = state.players[1].library[-1]
    state.cards[nonbasic].type_line = "Creature — Elf"
    state.cards[nonbasic].types = ["Creature"]
    spell = CardInstance(
        id="cultivate-invalid",
        name="Cultivate",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        oracle_text="Search your library for up to two basic land cards, reveal those cards, put them into your hand, then shuffle.",
    )
    state.cards[spell.id] = spell
    hints = build_cast_hints(state, spell, 1)
    ok, error = validate_cast_choice(hints, {"search_card_ids": [nonbasic]})
    assert ok is False
    assert "search restriction" in error.lower()


def test_topdeck_battlefield_tutor_exposes_and_resolves_explicit_selection() -> None:
    state = _state_with_searcher()
    top_ids = state.players[1].library[-6:]
    for index, cid in enumerate(top_ids):
        card = state.cards[cid]
        if index in {0, 2, 4}:
            card.types = ["Creature"]
            card.type_line = "Creature — Elf"
            card.power = 2 + index
            card.toughness = 2
            card.mana_cost = "{2}{G}"
        else:
            card.types = ["Land"]
            card.type_line = "Basic Land — Forest"
            card.mana_cost = ""
    spell = CardInstance(
        id="company-choice",
        name="Collected Company",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        oracle_text="Look at the top six cards of your library. Put up to two creature cards with mana value 3 or less from among them onto the battlefield.",
    )
    state.cards[spell.id] = spell

    hints = build_cast_hints(state, spell, 1)
    candidates = hints["topdeck_choice"]["candidates"]
    assert {item["id"] for item in candidates} == {top_ids[0], top_ids[2], top_ids[4]}
    chosen = [top_ids[0], top_ids[4]]
    ok, error = validate_cast_choice(hints, {"topdeck_card_ids": chosen})
    assert ok is True, error

    spec = build_ability_spec(state, spell, 1, {"topdeck_card_ids": chosen})
    assert spec.effect.payload["selected_card_ids"] == chosen
    resolve_effect(state, 1, spec.effect.key, spec.effect.payload)
    assert all(cid in state.players[1].battlefield for cid in chosen)
    assert top_ids[2] in state.players[1].library


def test_topdeck_battlefield_tutor_rejects_nonmatching_selection() -> None:
    state = _state_with_searcher()
    top_ids = state.players[1].library[-6:]
    for cid in top_ids:
        state.cards[cid].types = ["Land"]
        state.cards[cid].type_line = "Basic Land — Forest"
    spell = CardInstance(
        id="company-invalid-choice",
        name="Collected Company",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        oracle_text="Look at the top six cards of your library. Put up to two creature cards with mana value 3 or less from among them onto the battlefield.",
    )
    state.cards[spell.id] = spell
    hints = build_cast_hints(state, spell, 1)
    ok, error = validate_cast_choice(hints, {"topdeck_card_ids": [top_ids[0]]})
    assert ok is False
    assert "topdeck card" in error.lower()
