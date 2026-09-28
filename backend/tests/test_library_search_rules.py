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


def test_topdeck_battlefield_tutor_chooses_only_at_resolution() -> None:
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
    assert hints["topdeck_choice"] == {"top_n": 6, "max_count": 2, "allow_zero": True}
    assert not any(cid in str(hints) for cid in top_ids)
    chosen = [top_ids[0], top_ids[4]]
    ok, error = validate_cast_choice(hints, {"topdeck_card_ids": chosen})
    assert ok is False and "when the effect resolves" in error

    spec = build_ability_spec(state, spell, 1)
    assert "selected_card_ids" not in spec.effect.payload
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    resolve_effect(state, 1, spec.effect.key, spec.effect.payload)
    assert set(state.pending_mechanic_choice["options"]) == {top_ids[0], top_ids[2], top_ids[4]}
    from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
    from rules_engine.engine import RulesEngine
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    RulesEngine().take_action(state, 1, {"type": "choose_mechanic", "card_ids": chosen}, reject_invalid=True)
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
    assert "when the effect resolves" in error.lower()


def test_topdeck_put_uses_resolution_library_and_resumes_stack_after_snapshot() -> None:
    from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
    from rules_engine.engine import RulesEngine
    from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack

    state = _state_with_searcher()
    player = state.players[1]
    top = player.library[-5:]
    for cid in top:
        card = state.cards[cid]
        card.types = ["Creature"]
        card.type_line = "Creature - Elf"
        card.name = "Llanowar Elves"
        card.mana_cost = "{G}"
    spell = CardInstance(
        id="topdeck-spell", name="Storm the Festival", owner=1, controller=1,
        zone=Zone.STACK, types=["Sorcery"],
        oracle_text="Look at the top five cards of your library. You may put up to two permanent cards with mana value 5 or less from among them onto the battlefield. Put the rest on the bottom of your library in a random order.",
    )
    state.cards[spell.id] = spell
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    spec = build_ability_spec(state, spell, 1)
    assert spec.effect.key == "topdeck_put_permanents_battlefield"
    hints = build_cast_hints(state, spell, 1)
    assert not any(cid in str(hints) for cid in top)
    add_to_stack(state, spell.id, 1, spell.name, spec.effect.key, spec.effect.payload)
    # A response changes the library before this spell resolves.
    old_top = player.library.pop()
    player.library.insert(0, old_top)
    actual_top = player.library[-5:]
    resolve_top_of_stack(state)
    assert state.pending_mechanic_choice["top_ids"] == actual_top
    assert state.pending_mechanic_choice["resolving_item"]
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    RulesEngine().take_action(restored, 1, {"type": "choose_mechanic", "card_ids": [actual_top[-1]]}, reject_invalid=True)
    assert actual_top[-1] in restored.players[1].battlefield
    assert restored.pending_mechanic_choice is None
    assert not restored.stack
    assert spell.id in restored.players[1].graveyard


def test_topdeck_put_may_choose_zero_and_rejects_more_than_limit() -> None:
    from rules_engine.action_validation import ActionRejected
    from rules_engine.engine import RulesEngine
    import pytest

    state = _state_with_searcher()
    top = state.players[1].library[-6:]
    for cid in top:
        state.cards[cid].types = ["Creature"]
        state.cards[cid].mana_cost = "{G}"
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    resolve_effect(state, 1, "topdeck_put_creatures_battlefield", {"top_n": 6, "max_creatures": 2, "mv_max": 3})
    assert state.pending_mechanic_choice
    with pytest.raises(ActionRejected):
        RulesEngine().take_action(state, 1, {"type": "choose_mechanic", "card_ids": top[:3]}, reject_invalid=True)
    assert state.pending_mechanic_choice
    RulesEngine().take_action(state, 1, {"type": "choose_mechanic", "card_ids": []}, reject_invalid=True)
    assert state.pending_mechanic_choice is None
    assert not any(cid in state.players[1].battlefield for cid in top)


def test_topdeck_creature_mana_value_counts_colorless_symbol() -> None:
    state = _state_with_searcher()
    top = state.players[1].library[-2:]
    costly, eligible = top
    state.cards[costly].name = "Thought-Knot Seer"
    state.cards[costly].types = ["Creature"]
    state.cards[costly].mana_cost = "{3}{C}"
    state.cards[eligible].name = "Llanowar Elves"
    state.cards[eligible].types = ["Creature"]
    state.cards[eligible].mana_cost = "{G}"
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    resolve_effect(state, 1, "topdeck_put_creatures_battlefield", {"top_n": 2, "max_creatures": 2, "mv_max": 3})
    assert state.pending_mechanic_choice["options"] == [eligible]


def test_http_topdeck_put_choice_is_offered_only_after_resolution() -> None:
    from fastapi.testclient import TestClient
    from main import ACTIVE_MATCHES, MatchController, app
    from rules_engine.engine import RulesEngine

    state = _state_with_searcher()
    top = state.players[1].library[-6:]
    for cid in top:
        state.cards[cid].types = ["Creature"]
        state.cards[cid].name = "Llanowar Elves"
        state.cards[cid].mana_cost = "{G}"
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    resolve_effect(state, 1, "topdeck_put_creatures_battlefield", {"top_n": 6, "max_creatures": 2, "mv_max": 3})
    deck = [{"quantity": 60, "card_name": "Forest"}]
    match = MatchController(
        state=state, rules=RulesEngine(), controllers={1: "human", 2: "ai"}, ai={},
        mode="player_vs_ai", deck_ids=(None, None), mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3,
    )
    with TestClient(app) as client:
        ACTIVE_MATCHES[state.id] = match
        try:
            legal = client.get(f"/matches/{state.id}/legal-moves")
            assert legal.status_code == 200
            move = legal.json()["moves"][0]
            assert move["kind"] == "topdeck_put" and move["count"] == 2
            assert set(move["options"]) == set(top)
            selected = client.post(f"/matches/{state.id}/action", json={
                "player_id": 1, "action": {"type": "choose_mechanic", "card_ids": [top[-1]]},
            })
            assert selected.status_code == 200
            assert selected.json()["pending_mechanic_choice"] is None
            assert any(card["id"] == top[-1] for card in selected.json()["players"]["1"]["battlefield"])
        finally:
            ACTIVE_MATCHES.pop(state.id, None)
