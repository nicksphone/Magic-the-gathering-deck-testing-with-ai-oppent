"""AI sideboarding is legal, matchup-aware, and does not read hidden zones."""

from fastapi.testclient import TestClient
from sqlmodel import Session

from ai.agent import AIAgent
from ai.sideboarding import plan_sideboard
from card_data.hydration import hydrate_deck_cards
from game_state.state import CardInstance, MatchFactory, Zone
from main import ACTIVE_MATCHES, MatchController, _persist_active_match, _restore_active_matches, _start_next_game_state, app
from persistence.db import engine, init_db
from persistence.repository import Repository
from rules_engine.engine import RulesEngine


MAIN = [{"quantity": 26, "card_name": "Swamp"}, {"quantity": 26, "card_name": "Forest"},
        {"quantity": 8, "card_name": "Fatal Push"}]
SIDE = [{"quantity": 4, "card_name": "Abrupt Decay"}]
OPPONENT = [{"quantity": 60, "card_name": "Island"}]


def _decks():
    return hydrate_deck_cards(None, MAIN), hydrate_deck_cards(None, SIDE)


def test_ai_plans_artifact_answer_only_from_public_evidence():
    main, side = _decks()
    out, into = plan_sideboard(main, side, {"Artifact"})
    assert out == [{"card_name": "Fatal Push", "quantity": 4}]
    assert into == [{"card_name": "Abrupt Decay", "quantity": 4}]
    assert plan_sideboard(main, side, set()) == ([], [])
    assert plan_sideboard(main, side, {"Creature"}) == ([], [])


def test_ai_refuses_off_color_sideboard_card():
    main = hydrate_deck_cards(None, [{"quantity": 56, "card_name": "Swamp"},
                                     {"quantity": 4, "card_name": "Fatal Push"}])
    side = hydrate_deck_cards(None, SIDE)
    assert plan_sideboard(main, side, {"Enchantment"}) == ([], [])


def test_http_next_game_applies_ai_swaps_without_revealing_names():
    init_db()
    main, side = _decks()
    opponent = hydrate_deck_cards(None, OPPONENT)
    state = MatchFactory.from_decks(main, opponent, seed=71)
    state.winner = 2
    state.score = {1: 0, 2: 1}
    artifact = CardInstance(id="seen-artifact", name="Sol Ring", owner=2, controller=2,
                            zone=Zone.BATTLEFIELD, types=["Artifact"], type_line="Artifact")
    state.cards[artifact.id] = artifact
    state.players[2].battlefield.append(artifact.id)
    match = MatchController(
        state=state, rules=RulesEngine(), controllers={1: "ai", 2: "human"},
        ai={1: AIAgent(archetype="Midrange", opponent_archetype="Control"), 2: AIAgent()},
        mode="player_vs_ai", deck_ids=(None, None),
        mainboards={1: main, 2: opponent}, sideboards={1: side, 2: []},
        game_number=1, current_game_recorded=True, match_complete=False,
        best_of=3, root_seed=71,
    )
    ACTIVE_MATCHES[state.id] = match
    try:
        with Session(engine) as session:
            _persist_active_match(Repository(session), match)
        with TestClient(app) as client:
            response = client.post(f"/matches/{state.id}/next-game")
            assert response.status_code == 200, response.text
            view = response.json()
            active = ACTIVE_MATCHES[state.id]
            assert view["game_number"] == 2
            assert "1" not in view.get("sideboarding", {})
            assert sum(item["quantity"] for item in active.mainboards[1]) == 60
            assert {item["card_name"]: item["quantity"] for item in active.mainboards[1]}["Abrupt Decay"] == 4
            assert any("sideboards 4 card(s)" in line for line in view["log"])
            assert not any("sideboards 4 Abrupt Decay" in line for line in view["log"])
            ACTIVE_MATCHES.pop(state.id)
            with Session(engine) as session:
                _restore_active_matches(Repository(session), state.id)
            restored = ACTIVE_MATCHES[state.id]
            assert restored.game_number == 2
            assert {item["card_name"]: item["quantity"] for item in restored.mainboards[1]}["Abrupt Decay"] == 4
    finally:
        ACTIVE_MATCHES.pop(state.id, None)


def test_match_start_hydrates_sideboard_cards_for_ai():
    with TestClient(app) as client:
        response = client.post("/matches/start", json={
            "deck_a": MAIN, "deck_b": OPPONENT,
            "deck_a_sideboard": SIDE,
            "controller_a": "ai", "controller_b": "human",
        })
        assert response.status_code == 200, response.text
        match_id = response.json()["id"]
        try:
            card = ACTIVE_MATCHES[match_id].sideboards[1][0]
            assert card["card_name"] == "Abrupt Decay"
            assert card["mana_cost"] == "{B}{G}"
            assert "destroy target nonland permanent" in card["oracle_text"].lower()
        finally:
            ACTIVE_MATCHES.pop(match_id, None)


def test_full_ai_autoplay_sideboards_before_game_two():
    init_db()
    main = hydrate_deck_cards(None, [{"quantity": 56, "card_name": "Island"},
                                     {"quantity": 4, "card_name": "Fatal Push"}])
    side = hydrate_deck_cards(None, [{"quantity": 2, "card_name": "Counterspell"}])
    opponent = hydrate_deck_cards(None, OPPONENT)
    state = MatchFactory.from_decks(main, opponent, seed=72)
    state.winner = 2
    state.score = {1: 0, 2: 0}
    match = MatchController(
        state=state, rules=RulesEngine(), controllers={1: "ai", 2: "ai"},
        ai={1: AIAgent(archetype="Control", opponent_archetype="Control"),
            2: AIAgent(archetype="Control", opponent_archetype="Control")},
        mode="ai_vs_ai", deck_ids=(None, None), mainboards={1: main, 2: opponent},
        sideboards={1: side, 2: []}, game_number=1,
        current_game_recorded=False, match_complete=False, best_of=3, root_seed=72,
    )
    ACTIVE_MATCHES[state.id] = match
    try:
        with Session(engine) as session:
            _persist_active_match(Repository(session), match)
        with TestClient(app) as client:
            response = client.post(f"/matches/{state.id}/autoplay?ticks=1")
            assert response.status_code == 200, response.text
            assert response.json()["game_number"] == 2
            active = ACTIVE_MATCHES[state.id]
            assert sum(item["quantity"] for item in active.mainboards[1]) == 60
            assert {item["card_name"]: item["quantity"] for item in active.mainboards[1]}["Counterspell"] == 2
            pool = active.state.players[1].hand + active.state.players[1].library
            assert sum(active.state.cards[cid].name == "Counterspell" for cid in pool) == 2
    finally:
        ACTIVE_MATCHES.pop(state.id, None)


def test_ai_vs_human_uses_public_spells_not_hidden_cards_or_internal_archetype():
    main = hydrate_deck_cards(None, [{"quantity": 56, "card_name": "Island"},
                                     {"quantity": 4, "card_name": "Fatal Push"}])
    side = hydrate_deck_cards(None, [{"quantity": 2, "card_name": "Counterspell"}])
    opponent = hydrate_deck_cards(None, OPPONENT)

    def match_with_observation(public: bool) -> MatchController:
        state = MatchFactory.from_decks(main, opponent, seed=73)
        state.winner = 2
        state.score = {1: 0, 2: 1}
        seen = CardInstance(id="observed-spell", name="Counterspell", owner=2, controller=2,
                            zone=Zone.GRAVEYARD if public else Zone.HAND,
                            types=["Instant"], type_line="Instant")
        state.cards[seen.id] = seen
        (state.players[2].graveyard if public else state.players[2].hand).append(seen.id)
        return MatchController(
            state=state, rules=RulesEngine(), controllers={1: "ai", 2: "human"},
            ai={1: AIAgent(archetype="Control", opponent_archetype="Control"), 2: AIAgent()},
            mode="player_vs_ai", deck_ids=(None, None), mainboards={1: main, 2: opponent},
            sideboards={1: side, 2: []}, game_number=1,
            current_game_recorded=True, match_complete=False, best_of=3, root_seed=73,
        )

    hidden = match_with_observation(False)
    _start_next_game_state(hidden)
    assert not any(item["card_name"] == "Counterspell" for item in hidden.mainboards[1])

    public = match_with_observation(True)
    _start_next_game_state(public)
    assert {item["card_name"]: item["quantity"] for item in public.mainboards[1]}["Counterspell"] == 2
