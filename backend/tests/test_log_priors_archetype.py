"""Synthetic trace/component controls, not games or learned training evidence."""
from copy import deepcopy
import json

import pytest

from ai.agent import AIAgent
from ai.log_priors import build_priors_from_examples, build_priors_from_logs
from analytics.decision_quality import build_trace_payload
from game_state.state import CardInstance, MatchState, PlayerState, Zone
from scripts.extract_training_examples import _feature_row
from training.dataset import baseline_teacher_config


def trace(turn=2, pid=1, context="Aggro", **extra):
    row = {"pid": pid, "turn": turn, "hand": ["Sample Spell"],
           "action": {"type": "cast_spell", "card_name": "Sample Spell"},
           "opp_archetype": context}
    row.update(extra)
    return "AI TRACE " + json.dumps(row)


def logs():
    return [[item for context, turn in (("Aggro", 2), ("Control", 9))
             for _ in range(3) for item in
             (trace(turn, context=context), "Player A casts/activates Sample Spell.")]]


def examples():
    return [{"game": 1, "pid": 1, "turn": turn, "board_role_hint": "normal",
             "action_type": "cast_spell", "action_card_name": "Sample Spell",
             "opponent_archetype": context}
            for context, turn in (("Aggro", 2), ("Control", 9)) for _ in range(3)]


def card_row(payload):
    return payload["cards"]["sample spell"]


def timing(casts=3, turn=9):
    return {"casts": casts, "avg_turn": float(turn),
            "early_turn_cast_rate": float(turn <= 3),
            "mid_turn_cast_rate": float(4 <= turn <= 7),
            "late_turn_cast_rate": float(turn >= 8), "preferred_min_turn": turn - 1}


@pytest.mark.parametrize("builder,inputs", [(build_priors_from_logs, logs),
                                          (build_priors_from_examples, examples)])
def test_separate_known_context_rows_and_exact_legacy_aggregate(builder, inputs):
    labeled = inputs()
    before = deepcopy(labeled)
    legacy = examples() if builder is build_priors_from_examples else logs()
    if builder is build_priors_from_examples:
        for row in legacy:
            row.pop("opponent_archetype")
    else:
        legacy = [[line.replace(', "opp_archetype": "Aggro"', '')
                   .replace(', "opp_archetype": "Control"', '') for line in legacy[0]]]
    payload = builder(labeled)
    row = card_row(payload)
    assert row.pop("opponent_archetypes") == {"aggro": timing(turn=2), "control": timing()}
    assert payload == builder(legacy)
    assert labeled == before


@pytest.mark.parametrize("bad", [None, "", "unknown", "Other", "private-deck-name", 1,
                                 True, [], {}, ["Aggro"], {"name": "Aggro"}])
def test_bad_context_is_unavailable_not_inferred(bad):
    rows = examples()
    for row in rows:
        row["opponent_archetype"] = bad
    legacy = [{k: v for k, v in row.items() if k != "opponent_archetype"} for row in rows]
    assert build_priors_from_examples(rows) == build_priors_from_examples(legacy)


def test_alias_validation_and_conflicting_labels():
    rows = examples()
    for row in rows:
        row["opp_archetype"] = " " + row.pop("opponent_archetype").upper() + " "
    assert set(card_row(build_priors_from_examples(rows))["opponent_archetypes"]) == {"aggro", "control"}
    for row in rows:
        row["opponent_archetype"] = "Burn"
    assert "opponent_archetypes" not in card_row(build_priors_from_examples(rows))


@pytest.mark.parametrize("counts", [(3, 2), (2, 3), (5, 0), (2, 2)])
def test_both_contexts_need_three_casts(counts):
    rows = examples()[:counts[0]] + examples()[3:3 + counts[1]]
    assert all("opponent_archetypes" not in row for row in build_priors_from_examples(rows)["cards"].values())


@pytest.mark.parametrize("pid", [1, 2])
def test_actor_association_consumption_and_reset(pid):
    own, other = ("Player A", "Player B") if pid == 1 else ("Player B", "Player A")
    lines = []
    for context, turn in (("Aggro", 2), ("Control", 9)):
        for _ in range(3):
            lines += [trace(turn, pid, context), f"{own} casts/activates Sample Spell.",
                      f"{other} casts/activates Sample Spell."]
        # Wrong actor, pass, wrong card and malformed trace must not retain a label.
        lines += [trace(turn, pid, context), f"{other} casts/activates Sample Spell.",
                  f"{own} casts/activates Sample Spell.",
                  trace(turn, pid, context, action={"type": "pass_priority"}),
                  f"{own} casts/activates Sample Spell.",
                  trace(turn, pid, context), f"{own} casts/activates Different Spell.",
                  f"{own} casts/activates Sample Spell.",
                  trace(turn, pid, context), 'AI TRACE {"turn": broken}',
                  f"{own} casts/activates Sample Spell."]
    row = card_row(build_priors_from_logs([lines]))
    assert row["opponent_archetypes"] == {"aggro": timing(turn=2), "control": timing()}
    assert row["casts"] == 22


def test_custom_actor_requires_explicit_name_and_no_cross_game_trace():
    lines = [line.replace("Player A", "Custom seat") for line in logs()[0]]
    assert "opponent_archetypes" not in card_row(build_priors_from_logs([lines]))
    named = [line.replace('"pid": 1', '"pid": 1, "player_name": "Custom seat"') for line in lines]
    assert len(card_row(build_priors_from_logs([named]))["opponent_archetypes"]) == 2
    split = [[trace(context="Aggro")], ["Player A casts/activates Sample Spell."] * 3]
    assert "opponent_archetypes" not in card_row(build_priors_from_logs(split))


def test_merge_contexts_is_weighted_deterministic_and_no_aliases():
    from scripts.build_ai_log_priors import _merge_card_rows, _merge_priors
    left = {**timing(6, 2), "seen_in_logs": 6, "board_roles": {"normal": timing(6, 2)},
            "opponent_archetypes": {"aggro": timing(3, 2), "control": timing(3, 8)}}
    right = {**timing(6, 9), "seen_in_logs": 6, "board_roles": {"normal": timing(6, 9)},
             "opponent_archetypes": {"aggro": timing(3, 4), "control": timing(3, 10)}}
    before = deepcopy((left, right))
    merged = _merge_card_rows(left, right)
    assert merged["opponent_archetypes"]["aggro"]["casts"] == 6
    assert merged["opponent_archetypes"]["aggro"]["avg_turn"] == 3.0
    assert merged == _merge_card_rows(right, left)
    assert (left, right) == before
    merged["board_roles"]["normal"]["casts"] = 99
    merged["opponent_archetypes"]["aggro"]["casts"] = 99
    copied = _merge_priors({"cards": {"sample spell": left}}, {})
    copied["cards"]["sample spell"]["opponent_archetypes"]["aggro"]["casts"] = 99
    assert (left, right) == before


def position():
    state = MatchState(id="synthetic-component", players={pid: PlayerState(pid, f"seat {pid}") for pid in (1, 2)},
                       cards={}, stack=[], turn=2)
    card = CardInstance(id="sample", name="Sample Spell", owner=1, controller=1,
                        zone=Zone.HAND, types=["Sorcery"], type_line="Sorcery")
    return state, card


@pytest.mark.parametrize("context,expected", [("Aggro", 0.0), (" CONTROL ", -3.5), (None, 0.0),
                                               ("unknown", 0.0), ("unlisted", 0.0), (True, 0.0),
                                               ([], 0.0), ({}, 0.0)])
def test_actual_agent_matchup_selection_and_unknown_fallback(monkeypatch, context, expected):
    state, card = position()
    row = card_row(build_priors_from_examples(examples()))
    monkeypatch.setattr(AIAgent, "_log_priors_cache", {"cards": {"sample spell": row}})
    agent = AIAgent(opponent_archetype=None)
    agent.opponent_archetype = context
    assert agent._historical_cast_timing_bias(state, card, 1) == expected


@pytest.mark.parametrize("casts", [0, 2, 3, 5, 6])
def test_aggregate_gate_and_role_fallback_are_unchanged(monkeypatch, casts):
    state, card = position()
    row = {**timing(casts, 2), "board_roles": {"normal": timing(3, 9)},
           "opponent_archetypes": {"aggro": timing(2, 2), "control": timing(3, 9)}}
    monkeypatch.setattr(AIAgent, "_log_priors_cache", {"cards": {"sample spell": row}})
    assert AIAgent(opponent_archetype="Aggro")._historical_cast_timing_bias(state, card, 1) == (-3.5 if casts >= 6 else 0.0)


def test_producer_and_teacher_context_remain_unavailable():
    state, _ = position()
    payload = build_trace_payload(state, 1, [], {"type": "pass_priority"})
    assert "opp_archetype" not in payload and "opponent_archetype" not in payload
    assert "opponent_archetype" not in _feature_row({"game": 1}, payload)
    assert baseline_teacher_config("strong")["opponent_archetype"] is None


def test_builder_import_has_no_live_db_dependency():
    import ast
    import inspect
    from scripts import build_ai_log_priors
    tree = ast.parse(inspect.getsource(build_ai_log_priors))
    assert not any(isinstance(node, ast.ImportFrom) and node.module == "persistence.db"
                   for node in tree.body)
    assert not hasattr(build_ai_log_priors, "engine")


def test_precollection_pure_io_canaries():
    import _socket
    import _sqlite3
    import os
    import socket
    import sqlite3
    import subprocess
    if os.environ.get("TASK33_PURE_GUARD") != "1":
        pytest.skip("Run with the archived precollection pure guard")
    for call in (lambda: sqlite3.connect(":memory:"), lambda: _sqlite3.connect(":memory:"),
                 lambda: sqlite3.dbapi2.connect(":memory:"), lambda: socket.socket(),
                 lambda: _socket.socket(), lambda: socket.socket.__new__(socket.socket),
                 lambda: _socket.socket.__new__(_socket.socket),
                 lambda: subprocess.Popen(["true"]), lambda: os.system("true"),
                 lambda: __import__("openai")):
        with pytest.raises(RuntimeError, match="pure guard"):
            call()


def write_exports(root, *, overlap=True, provenance=True, conflict=False):
    root.mkdir()
    lines = []
    rows = examples()
    for index, row in enumerate(rows):
        source = json.loads(trace(row["turn"], context=row["opponent_archetype"])[len("AI TRACE "):])
        if provenance:
            source["action_index"] = index
            row["action_index"] = index
        lines.extend(["AI TRACE " + json.dumps(source), "Player A casts/activates Sample Spell."])
    (root / "games.jsonl").write_text(json.dumps({"game": 1, "log": lines}) + "\n")
    if not overlap:
        rows = []
    if conflict:
        for row in rows:
            row["turn"] += 1
    (root / "training_examples.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    return lines, rows


def test_offline_context_reconciliation_dedups_only_provenance_not_aggregate(tmp_path, monkeypatch, capsys):
    from scripts import build_ai_log_priors as cli
    root = tmp_path / "exports"
    write_exports(root)
    original = {p: p.read_bytes() for p in root.iterdir()}
    saved = []
    monkeypatch.setattr(cli, "save_log_priors", lambda payload: saved.append(deepcopy(payload)) or payload)
    cli.main(["--training-root", str(root)])
    row = card_row(saved[0])
    assert row["casts"] == 12  # Six log casts plus six exported examples, exactly legacy.
    assert row["opponent_archetypes"] == {"aggro": timing(turn=2), "control": timing()}
    assert {p: p.read_bytes() for p in root.iterdir()} == original
    assert json.loads(capsys.readouterr().out)["context_available"] is True


@pytest.mark.parametrize("provenance,conflict,reason", [(False, False, "missing_action_provenance"),
                                                        (True, True, "conflicting_action_provenance")])
def test_offline_unavailable_context_no_artifact(tmp_path, monkeypatch, capsys, provenance, conflict, reason):
    from scripts import build_ai_log_priors as cli
    root = tmp_path / "exports"
    write_exports(root, provenance=provenance, conflict=conflict)
    saved = []
    monkeypatch.setattr(cli, "save_log_priors", lambda payload: saved.append(payload) or payload)
    cli.main(["--training-root", str(root)])
    assert saved == []
    report = json.loads(capsys.readouterr().out)
    assert report["context_available"] is False
    assert report["context_unavailable"][reason] == 12


def test_context_threshold_applies_after_disjoint_logs_and_examples(tmp_path, monkeypatch):
    from scripts import build_ai_log_priors as cli
    root = tmp_path / "exports"
    lines, rows = write_exports(root)
    # Two raw log events and one distinct exported event per context, not a duplicate.
    (root / "games.jsonl").write_text(json.dumps({"game": 1, "log": lines[:4] + lines[6:10]}) + "\n")
    (root / "training_examples.jsonl").write_text("".join(json.dumps(rows[i]) + "\n" for i in (2, 5)))
    saved = []
    monkeypatch.setattr(cli, "save_log_priors", lambda payload: saved.append(payload) or payload)
    cli.main(["--training-root", str(root)])
    assert card_row(saved[0])["opponent_archetypes"] == {"aggro": timing(turn=2), "control": timing()}


@pytest.mark.parametrize("bad", [None, "unknown", 7, True])
def test_invalid_prior_context_keys_do_not_override_role(monkeypatch, bad):
    state, card = position()
    row = {**timing(6, 2), "board_roles": {"normal": timing(3, 9)},
           "opponent_archetypes": {bad: timing(3, 2), "aggro": timing(3, 2)}}
    monkeypatch.setattr(AIAgent, "_log_priors_cache", {"cards": {"sample spell": row}})
    assert AIAgent(opponent_archetype="Aggro")._historical_cast_timing_bias(state, card, 1) == -3.5


def test_role_hintless_conflicting_export_invalidates_context_only(tmp_path, monkeypatch, capsys):
    from scripts import build_ai_log_priors as cli
    root = tmp_path / "synthetic-exports"
    _, rows = write_exports(root)
    rows[0].pop("board_role_hint")
    rows[0]["opponent_archetype"] = "Control"
    (root / "training_examples.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    before = {path: path.read_bytes() for path in root.iterdir()}
    legacy_examples = cli._read_training_run_examples(root)
    assert len(legacy_examples) == 5
    saved = []
    monkeypatch.setattr(cli, "save_log_priors", lambda payload: saved.append(payload) or payload)
    cli.main(["--training-root", str(root)])
    assert saved == []
    report = json.loads(capsys.readouterr().out)
    assert report["context_available"] is False
    assert report["context_unavailable"]["conflicting_action_provenance"] == 2
    assert cli._read_training_run_examples(root) == legacy_examples
    assert {path: path.read_bytes() for path in root.iterdir()} == before


def test_role_hintless_disjoint_export_adds_context_without_aggregate_counts(tmp_path, monkeypatch):
    from scripts import build_ai_log_priors as cli
    root = tmp_path / "synthetic-exports"
    lines, rows = write_exports(root)
    lines = lines[:4] + lines[6:10]
    rows = [rows[2], rows[5]]
    for row in rows:
        row.pop("board_role_hint")
    (root / "games.jsonl").write_text(json.dumps({"game": 1, "log": lines}) + "\n")
    (root / "training_examples.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    before = {path: path.read_bytes() for path in root.iterdir()}
    legacy = build_priors_from_logs([lines])
    assert cli._read_training_run_examples(root) == []
    saved = []
    monkeypatch.setattr(cli, "save_log_priors", lambda payload: saved.append(deepcopy(payload)) or payload)
    cli.main(["--training-root", str(root)])
    assert len(saved) == 1
    payload = saved[0]
    assert card_row(payload).pop("opponent_archetypes") == {"aggro": timing(turn=2), "control": timing()}
    assert payload == legacy
    assert card_row(payload)["casts"] == 4
    assert {path: path.read_bytes() for path in root.iterdir()} == before


@pytest.mark.parametrize("context", [None, "unknown", "Aggro", "Control"])
@pytest.mark.parametrize("field", ["avg_turn", "early_turn_cast_rate", "mid_turn_cast_rate",
                                  "late_turn_cast_rate", "preferred_min_turn"])
def test_oversized_context_timing_uses_byte_exact_actual_legacy_fallback(monkeypatch, context, field):
    import struct
    from ai.log_priors import _eligible_opponent_rows
    state, card = position()
    legacy_row = {**timing(6, 2), "board_roles": {"normal": timing(3, 9)}}
    monkeypatch.setattr(AIAgent, "_log_priors_cache", {"cards": {"sample spell": legacy_row}})
    agent = AIAgent(opponent_archetype=context)
    expected = agent._historical_cast_timing_bias(state, card, 1)
    malformed = timing(3, 2)
    malformed[field] = 10**400
    row = {**deepcopy(legacy_row), "opponent_archetypes": {"aggro": malformed, "control": timing()}}
    before = deepcopy(row)
    monkeypatch.setattr(AIAgent, "_log_priors_cache", {"cards": {"sample spell": row}})
    actual = agent._historical_cast_timing_bias(state, card, 1)
    assert struct.pack("!d", actual) == struct.pack("!d", expected)
    assert _eligible_opponent_rows(row["opponent_archetypes"]) == {}
    assert row == before


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan"), True, "9", []])
def test_nonfinite_or_typed_context_timing_is_unavailable(value):
    from ai.log_priors import _eligible_opponent_rows
    malformed = timing()
    malformed["avg_turn"] = value
    rows = {"aggro": malformed, "control": timing()}
    assert _eligible_opponent_rows(rows) == {}


@pytest.mark.parametrize("action_type", [[], {}])
def test_role_hintless_unhashable_action_type_is_skipped_without_touching_exports(tmp_path, monkeypatch, action_type):
    from scripts import build_ai_log_priors as cli
    root = tmp_path / "synthetic-exports"
    _, rows = write_exports(root)
    rows.append({"action_type": action_type})
    (root / "training_examples.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    before = {path: path.read_bytes() for path in root.iterdir()}
    aggregate_inputs = cli._read_training_run_examples(root)
    assert len(aggregate_inputs) == 6
    saved = []
    monkeypatch.setattr(cli, "save_log_priors", lambda payload: saved.append(deepcopy(payload)) or payload)
    cli.main(["--training-root", str(root)])
    assert len(saved) == 1
    payload = saved[0]
    assert card_row(payload).pop("opponent_archetypes") == {"aggro": timing(turn=2), "control": timing()}
    legacy = cli._merge_priors(build_priors_from_logs(cli._read_training_run_logs(root)),
                              build_priors_from_examples(aggregate_inputs))
    card_row(legacy).pop("opponent_archetypes")
    assert payload == legacy
    assert cli._read_training_run_examples(root) == aggregate_inputs
    assert {path: path.read_bytes() for path in root.iterdir()} == before


def test_role_hintless_oversized_turn_is_unavailable_before_payload_math(tmp_path, monkeypatch, capsys):
    from scripts import build_ai_log_priors as cli
    root = tmp_path / "synthetic-exports"
    _, rows = write_exports(root)
    rows.append({"game": 2, "action_index": 6, "pid": 1, "turn": 10**400,
                 "action_type": "cast_spell", "action_card_name": "Sample Spell",
                 "opp_archetype": "Aggro"})
    (root / "training_examples.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    before = {path: path.read_bytes() for path in root.iterdir()}
    assert len(cli._read_training_run_examples(root)) == 6
    saved = []
    monkeypatch.setattr(cli, "save_log_priors", lambda payload: saved.append(deepcopy(payload)) or payload)
    cli.main(["--training-root", str(root)])
    assert len(saved) == 1
    assert card_row(saved[0])["opponent_archetypes"] == {"aggro": timing(turn=2), "control": timing()}
    assert card_row(saved[0])["casts"] == 12
    assert json.loads(capsys.readouterr().out)["context_unavailable"]["invalid_context_turn"] == 1
    assert {path: path.read_bytes() for path in root.iterdir()} == before


def test_identifiable_noncast_duplicate_invalidates_conflicting_cast_context(tmp_path, monkeypatch, capsys):
    from scripts import build_ai_log_priors as cli
    root = tmp_path / "synthetic-exports"
    _, rows = write_exports(root)
    rows[0].pop("board_role_hint")
    rows[0]["action_type"] = "play_land"
    (root / "training_examples.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    before = {path: path.read_bytes() for path in root.iterdir()}
    assert len(cli._read_training_run_examples(root)) == 5
    saved = []
    monkeypatch.setattr(cli, "save_log_priors", lambda payload: saved.append(payload) or payload)
    cli.main(["--training-root", str(root)])
    assert saved == []
    report = json.loads(capsys.readouterr().out)
    assert report["context_available"] is False
    assert report["context_unavailable"]["conflicting_action_provenance"] == 2
    assert {path: path.read_bytes() for path in root.iterdir()} == before


@pytest.mark.parametrize("pid", [1, 2])
@pytest.mark.parametrize("context", [None, "unknown", "Aggro"])
@pytest.mark.parametrize("action_type", [[], {}])
def test_unhashable_trace_action_preserves_byte_exact_legacy_aggregate(pid, context, action_type):
    actor = "Player A" if pid == 1 else "Player B"
    lines = [item for _ in range(3) for item in
             (trace(pid=pid, context=context, action={"type": action_type, "card_name": "Sample Spell"}),
              f"{actor} casts/activates Sample Spell.")]
    before = deepcopy(lines)
    legacy_lines = [item for _ in range(3) for item in
                    (trace(pid=pid, context=None, action={"type": "pass_priority", "card_name": "Sample Spell"}),
                     f"{actor} casts/activates Sample Spell.")]
    actual = build_priors_from_logs([lines])
    expected = build_priors_from_logs([legacy_lines])
    assert json.dumps(actual, sort_keys=True).encode() == json.dumps(expected, sort_keys=True).encode()
    assert card_row(actual)["casts"] == 3
    assert "opponent_archetypes" not in card_row(actual)
    assert lines == before
