from __future__ import annotations

from sqlmodel import Session

from ai.agent import AIAgent, AIDecision
from game_state.state import CardInstance, MatchFactory, Step, Zone
from main import ACTIVE_MATCHES, MatchController, _force_ai_land_action, autoplay_tick
from persistence.db import engine, init_db
from persistence.repository import Repository
from rules_engine.engine import RulesEngine


def test_autoplay_preserves_first_strike_priority_window(monkeypatch) -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=91)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.DECLARE_BLOCKERS
    state.active_player = state.priority_player = 1
    state.blockers_declared = True
    creature = CardInstance(
        id="swiftblade", name="Boros Swiftblade", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Creature"], power=1, toughness=2,
        keywords=["double strike"], summoning_sick=False,
    )
    state.cards[creature.id] = creature
    state.players[1].battlefield.append(creature.id)
    state.attackers = [creature.id]
    state.attack_targets = {creature.id: "player:2"}
    match = MatchController(
        state=state, rules=RulesEngine(), controllers={1: "ai", 2: "ai"},
        ai={1: AIAgent(difficulty="strong"), 2: AIAgent(difficulty="strong")},
        mode="ai_vs_ai", deck_ids=(None, None), mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3,
    )
    monkeypatch.setattr(AIAgent, "choose_action", lambda self, state, legal, pid: AIDecision({"type": "pass_priority"}, "test"))
    ACTIVE_MATCHES[state.id] = match
    init_db()
    try:
        with Session(engine) as session:
            first = autoplay_tick(state.id, ticks=2, repo=Repository(session))
            assert first["step"] == Step.COMBAT_DAMAGE
            assert first["combat_damage_stage"] == "first"
            assert first["players"][2]["life"] == 19
            second = autoplay_tick(state.id, ticks=2, repo=Repository(session))
            assert second["combat_damage_stage"] == "regular"
            assert second["players"][2]["life"] == 18
    finally:
        ACTIVE_MATCHES.pop(state.id, None)


def test_autoplay_advances_to_next_game_for_full_ai_match() -> None:
    deck_a = [{"quantity": 60, "card_name": "Lightning Bolt"}]
    deck_b = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck_a, deck_b)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.winner = 1
    state.score = {1: 0, 2: 0}

    match = MatchController(
        state=state,
        rules=RulesEngine(),
        controllers={1: "ai", 2: "ai"},
        ai={1: AIAgent(difficulty="strong"), 2: AIAgent(difficulty="strong")},
        mode="ai_vs_ai",
        deck_ids=(None, None),
        mainboards={1: deck_a, 2: deck_b},
        sideboards={1: [], 2: []},
        game_number=1,
        current_game_recorded=False,
        match_complete=False,
        best_of=3,
    )
    ACTIVE_MATCHES[state.id] = match
    init_db()
    try:
        with Session(engine) as session:
            out = autoplay_tick(state.id, ticks=1, repo=Repository(session))
    finally:
        ACTIVE_MATCHES.pop(state.id, None)

    assert out["game_number"] == 2
    assert out["winner"] is None
    score = {str(k): v for k, v in out["score"].items()}
    assert score == {"1": 1, "2": 0}
    assert out["pregame_pending"] is True
    assert any("Starting game 2" in line for line in out["log"])


def test_autoplay_forces_ai_land_drop_on_own_main_phase() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = state.step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    p1 = state.players[1]
    p1.lands_played_this_turn = 0

    battlefield_before = len(p1.battlefield)
    hand_before = len(p1.hand)

    match = MatchController(
        state=state,
        rules=RulesEngine(),
        controllers={1: "ai", 2: "ai"},
        ai={1: AIAgent(difficulty="strong", archetype="Control"), 2: AIAgent(difficulty="strong", archetype="Control")},
        mode="ai_vs_ai",
        deck_ids=(None, None),
        mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []},
        game_number=1,
        current_game_recorded=False,
        match_complete=False,
        best_of=3,
    )
    ACTIVE_MATCHES[state.id] = match
    init_db()
    try:
        with Session(engine) as session:
            _ = autoplay_tick(state.id, ticks=1, repo=Repository(session))
    finally:
        ACTIVE_MATCHES.pop(state.id, None)

    assert len(match.state.players[1].battlefield) == battlefield_before + 1
    assert len(match.state.players[1].hand) == hand_before - 1
    assert match.state.players[1].lands_played_this_turn == 1


def test_autoplay_land_guard_overrides_ai_pass_when_land_is_legal() -> None:
    class PassOnlyAI:
        def choose_action(self, state, legal_moves, player_id):
            return AIDecision(action={"type": "pass_priority"}, reasoning="forced test pass")

    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = state.step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    p1 = state.players[1]
    p1.lands_played_this_turn = 0
    battlefield_before = len(p1.battlefield)

    match = MatchController(
        state=state,
        rules=RulesEngine(),
        controllers={1: "ai", 2: "ai"},
        ai={1: PassOnlyAI(), 2: PassOnlyAI()},
        mode="ai_vs_ai",
        deck_ids=(None, None),
        mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []},
        game_number=1,
        current_game_recorded=False,
        match_complete=False,
        best_of=3,
    )
    ACTIVE_MATCHES[state.id] = match
    init_db()
    try:
        with Session(engine) as session:
            _ = autoplay_tick(state.id, ticks=1, repo=Repository(session))
    finally:
        ACTIVE_MATCHES.pop(state.id, None)

    assert len(match.state.players[1].battlefield) == battlefield_before + 1
    assert match.state.players[1].lands_played_this_turn == 1


def test_land_guard_returns_offered_move_when_ai_names_another_card() -> None:
    class WrongLandAI:
        def choose_action(self, state, legal_moves, player_id):
            return AIDecision(action={"type": "play_land", "card_id": "not-in-hand"}, reasoning="bad card id")

    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = state.step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    rules = RulesEngine()
    match = MatchController(
        state=state, rules=rules, controllers={1: "ai", 2: "ai"},
        ai={1: WrongLandAI(), 2: WrongLandAI()}, mode="ai_vs_ai",
        deck_ids=(None, None), mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []}, game_number=1,
        current_game_recorded=False, match_complete=False, best_of=3,
    )
    offered = [move for move in rules.legal_moves(state, 1) if move["type"] == "play_land"]
    assert offered
    assert _force_ai_land_action(match, 1, offered) in offered


def test_autoplay_land_guard_overrides_ai_cast_when_land_is_legal() -> None:
    class CastOnlyAI:
        def choose_action(self, state, legal_moves, player_id):
            return AIDecision(action={"type": "cast_spell", "card_id": "fake-spell"}, reasoning="forced test cast")

    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = state.step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    p1 = state.players[1]
    p1.lands_played_this_turn = 0
    battlefield_before = len(p1.battlefield)

    match = MatchController(
        state=state,
        rules=RulesEngine(),
        controllers={1: "ai", 2: "ai"},
        ai={1: CastOnlyAI(), 2: CastOnlyAI()},
        mode="ai_vs_ai",
        deck_ids=(None, None),
        mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []},
        game_number=1,
        current_game_recorded=False,
        match_complete=False,
        best_of=3,
    )
    ACTIVE_MATCHES[state.id] = match
    init_db()
    try:
        with Session(engine) as session:
            _ = autoplay_tick(state.id, ticks=1, repo=Repository(session))
    finally:
        ACTIVE_MATCHES.pop(state.id, None)

    assert len(match.state.players[1].battlefield) == battlefield_before + 1
    assert match.state.players[1].lands_played_this_turn == 1


def test_autoplay_does_not_invent_land_move_when_rules_omit_it() -> None:
    class LegalDropsLandRuleProxy:
        def __init__(self, wrapped: RulesEngine) -> None:
            self._wrapped = wrapped

        def legal_moves(self, state, player_id):
            moves = self._wrapped.legal_moves(state, player_id)
            return [m for m in moves if m.get("type") != "play_land"]

        def take_action(self, state, player_id, action, **kwargs):
            return self._wrapped.take_action(state, player_id, action, **kwargs)

        def advance_no_priority_step(self, state):
            return self._wrapped.advance_no_priority_step(state)

    class PassOnlyAI:
        def choose_action(self, state, legal_moves, player_id):
            return AIDecision(action={"type": "pass_priority"}, reasoning="forced test pass")

    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = state.step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    p1 = state.players[1]
    p1.lands_played_this_turn = 0
    battlefield_before = len(p1.battlefield)

    wrapped_rules = RulesEngine()
    match = MatchController(
        state=state,
        rules=LegalDropsLandRuleProxy(wrapped_rules),
        controllers={1: "ai", 2: "ai"},
        ai={1: PassOnlyAI(), 2: PassOnlyAI()},
        mode="ai_vs_ai",
        deck_ids=(None, None),
        mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []},
        game_number=1,
        current_game_recorded=False,
        match_complete=False,
        best_of=3,
    )
    ACTIVE_MATCHES[state.id] = match
    init_db()
    try:
        with Session(engine) as session:
            _ = autoplay_tick(state.id, ticks=1, repo=Repository(session))
    finally:
        ACTIVE_MATCHES.pop(state.id, None)

    assert len(match.state.players[1].battlefield) == battlefield_before
    assert match.state.players[1].lands_played_this_turn == 0


def test_autoplay_land_guard_ignores_stale_land_counter_drift() -> None:
    class PassOnlyAI:
        def choose_action(self, state, legal_moves, player_id):
            return AIDecision(action={"type": "pass_priority"}, reasoning="forced test pass")

    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = state.step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    p1 = state.players[1]
    # Simulate stale drift from a previous turn; legal move should still allow a land this turn.
    p1.lands_played_this_turn = 1
    p1.last_land_play_turn = 0
    p1.land_plays_recorded_on_turn = 0
    battlefield_before = len(p1.battlefield)

    match = MatchController(
        state=state,
        rules=RulesEngine(),
        controllers={1: "ai", 2: "ai"},
        ai={1: PassOnlyAI(), 2: PassOnlyAI()},
        mode="ai_vs_ai",
        deck_ids=(None, None),
        mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []},
        game_number=1,
        current_game_recorded=False,
        match_complete=False,
        best_of=3,
    )
    ACTIVE_MATCHES[state.id] = match
    init_db()
    try:
        with Session(engine) as session:
            _ = autoplay_tick(state.id, ticks=1, repo=Repository(session))
    finally:
        ACTIVE_MATCHES.pop(state.id, None)

    assert len(match.state.players[1].battlefield) == battlefield_before + 1
    assert match.state.players[1].last_land_play_turn == state.turn
