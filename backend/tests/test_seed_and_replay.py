from __future__ import annotations

from ai.agent import AIAgent
from game_state.state import MatchFactory
from main import ACTIVE_MATCHES, MatchController, get_match_replay
from rules_engine.engine import RulesEngine
from scripts.regression_matrix_replay import _normalize_log_line, classify_first_divergence, classify_log_line
from analytics.replay_tools import classify_timeout_state


def test_match_factory_seed_reproducible_openers() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    a = MatchFactory.from_decks(deck, deck, seed=123)
    b = MatchFactory.from_decks(deck, deck, seed=123)
    assert [a.cards[cid].name for cid in a.players[1].hand] == [b.cards[cid].name for cid in b.players[1].hand]
    assert [a.cards[cid].name for cid in a.players[2].hand] == [b.cards[cid].name for cid in b.players[2].hand]


def test_seeded_mulligans_are_reproducible_even_after_prior_random_use() -> None:
    deck = [
        {"quantity": 30, "card_name": "Island"},
        {"quantity": 30, "card_name": "Mountain"},
    ]
    a = MatchFactory.from_decks(deck, deck, seed=123)
    b = MatchFactory.from_decks(deck, deck, seed=123)
    engine = RulesEngine()

    engine.take_action(a, 1, {"type": "mulligan"})
    engine.take_action(b, 1, {"type": "mulligan"})

    assert [a.cards[cid].name for cid in a.players[1].hand] == [b.cards[cid].name for cid in b.players[1].hand]
    assert [a.cards[cid].name for cid in a.players[1].library[:10]] == [b.cards[cid].name for cid in b.players[1].library[:10]]


def test_replay_endpoint_returns_entries() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=7)
    state.log.extend(["Turn 1.", "Player A plays Island.", "Turn 2.", "Player B plays Island."])
    ctrl = MatchController(
        state=state,
        rules=RulesEngine(),
        controllers={1: "ai", 2: "ai"},
        ai={1: AIAgent(difficulty="master"), 2: AIAgent(difficulty="master")},
        mode="ai_vs_ai",
        deck_ids=(None, None),
        mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []},
        game_number=1,
        current_game_recorded=False,
        match_complete=False,
        best_of=3,
    )
    ACTIVE_MATCHES[state.id] = ctrl
    body = get_match_replay(state.id)
    assert body["match_id"] == state.id
    assert body["entry_count"] >= 4
    assert body["log_hash"]
    assert isinstance(body["entries"], list)
    assert len(body["entries"]) >= 4


def test_replay_log_normalization_masks_uuid_instances() -> None:
    left = "AI TRACE {\"action\":{\"card_id\":\"123e4567-e89b-12d3-a456-426614174000\"}}"
    right = "AI TRACE {\"action\":{\"card_id\":\"223e4567-e89b-12d3-a456-426614174999\"}}"
    assert _normalize_log_line(left) == _normalize_log_line(right)


def test_classify_log_line_detects_action_kind() -> None:
    assert classify_log_line('AI TRACE {"action":{"type":"cast_spell","card_name":"Lightning Bolt"}}') == "cast_spell"
    assert classify_log_line("Player A plays Island.") == "play_land"
    assert classify_log_line("Player B passes priority on precombat_main (stack=0).") == "pass_priority"


def test_classify_first_divergence_uses_action_labels() -> None:
    drift = {
        "index": 4,
        "a": 'AI TRACE {"action":{"type":"cast_spell","card_name":"Lightning Bolt"}}',
        "b": 'AI TRACE {"action":{"type":"pass_priority"}}',
        "context_before": ["Turn 4."],
        "context_after_a": [],
        "context_after_b": [],
    }
    label = classify_first_divergence(drift)
    assert label["category"] == "pass_vs_action"
    assert label["action_a"] == "cast_spell"
    assert label["action_b"] == "pass_priority"


def test_classify_first_divergence_includes_trace_context_summary() -> None:
    drift = {
        "index": 4,
        "a": 'AI TRACE {"pid":1,"turn":5,"step":"precombat_main","active_player":1,"priority_player":1,"hand":["Counterspell"],"opp_hand":["Threat"],"battlefield":[{"id":"c1","types":["Land"]}],"opp_battlefield":[{"id":"c2","types":["Creature"]}],"life":{"self":16,"opp":12},"legal_non_pass":true,"legal_has_land":false,"action":{"type":"cast_spell","card_name":"Counterspell"}}',
        "b": 'AI TRACE {"pid":1,"turn":5,"step":"precombat_main","active_player":1,"priority_player":1,"hand":["Counterspell"],"opp_hand":["Threat"],"battlefield":[{"id":"c1","types":["Land"]}],"opp_battlefield":[{"id":"c2","types":["Creature"]}],"life":{"self":16,"opp":12},"legal_non_pass":true,"legal_has_land":false,"action":{"type":"pass_priority"}}',
        "context_before": [],
        "context_after_a": [],
        "context_after_b": [],
    }

    label = classify_first_divergence(drift)

    assert label["trace_context_a"]["hand_size"] == 1
    assert label["trace_context_a"]["opp_hand_size"] == 1
    assert label["trace_context_a"]["battlefield_size"] == 1
    assert label["trace_context_a"]["opp_battlefield_size"] == 1
    assert label["trace_context_a"]["action_type"] == "cast_spell"
    assert label["trace_context_b"]["action_type"] == "pass_priority"


def test_classify_first_divergence_recognizes_attack_and_sacrifice_lines() -> None:
    attack = classify_first_divergence(
        {
            "index": 3,
            "a": "Attackers declared: Recruiter -> Player B",
            "b": "Attackers declared: Recruiter -> Player B",
            "context_before": [],
            "context_after_a": [],
            "context_after_b": [],
        }
    )
    sacrifice = classify_first_divergence(
        {
            "index": 4,
            "a": "Blood Artist sacrifices Bloodghast.",
            "b": "Blood Artist sacrifices Bloodghast.",
            "context_before": [],
            "context_after_a": [],
            "context_after_b": [],
        }
    )

    assert attack["action_a"] == "attack"
    assert attack["category"] == "attack"
    assert sacrifice["action_a"] == "sacrifice"
    assert sacrifice["category"] == "sacrifice"


def test_classify_timeout_state_distinguishes_long_game_and_stall() -> None:
    long_game_log = ["AI TRACE {\"turn\":1,\"action\":{\"type\":\"cast_spell\"}}"] * 12
    stall_log = [
        "Player A passes priority.",
        "Player B passes priority.",
        "Player A passes priority.",
        "Player B passes priority.",
        "Player A passes priority.",
    ]
    rules_log = ["Invalid targets for Secure the Wastes: X value is required and must be non-negative."]

    assert classify_timeout_state(long_game_log, True) == "timeout_long_game"
    assert classify_timeout_state(stall_log, True) == "likely_stall"
    assert classify_timeout_state(rules_log, True) == "timeout_rules_issue"
    assert classify_timeout_state([], False) == "resolved"
