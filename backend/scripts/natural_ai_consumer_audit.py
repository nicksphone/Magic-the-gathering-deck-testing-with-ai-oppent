"""Private, bounded diagnostics delegating to the pinned matrix replay harness."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

from scripts import regression_matrix_replay as matrix
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def write(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(canonical(value))
    temporary.replace(path)


def tuple_tree(value):
    return tuple(tuple_tree(v) for v in value) if isinstance(value, list) else value


def probe(path):
    record = json.loads(path.read_text())
    state = deserialize_match_snapshot(record["snapshot"])
    moves = matrix.RulesEngine().legal_moves(state, record["pid"])
    results = {}
    for mode in ("cold", "restored_memory"):
        agent = matrix.AIAgent(**record["config"])
        if mode == "restored_memory":
            agent._main_pass_signature_counts = {
                tuple_tree(key): value for key, value in record["agent_memory"]
            }
        before = digest(serialize_match_snapshot(state))
        decision = agent.choose_action(state, moves, record["pid"])
        results[mode] = {
            "action": matrix.complete_action(decision.action),
            "reasoning": decision.reasoning,
            "action_matches": matrix.complete_action(decision.action) == record["action"],
            "root_pure": before == digest(serialize_match_snapshot(state)),
        }
    write(path.parent / "restart-result.json", {
        "legal_matches": moves == record["legal_moves"],
        "codec_matches": serialize_match_snapshot(state) == record["snapshot"],
        "tick": record["tick"], "results": results,
    })


class SoftDeadline(Exception):
    pass


def game(evidence, case):
    policy = json.loads((evidence / "sample-policy.json").read_text())
    decks = json.loads((evidence / "deck-preflight.json").read_text())
    out = evidence / case["id"]
    out.mkdir(exist_ok=True)
    started = time.monotonic()
    context = {}
    latest = None
    stream = gzip.open(out / "decisions.jsonl.gz", "wt")
    checkpoint_chosen = False

    def emit(value):
        stream.write(canonical(value) + "\n")
        stream.flush()

    def observer(value):
        nonlocal context
        context = value
        write(out / "status.json", {**value, "pid_process": os.getpid(),
                                    "wall_seconds": time.monotonic() - started})
        emit({"event": "stage", **value})
        if time.monotonic() - started > policy["game_soft_wall_seconds"]:
            raise SoftDeadline("Predeclared between-stage wall deadline")

    original_agent = matrix.AIAgent
    original_rules = matrix.RulesEngine

    class ObservedAgent(original_agent):
        def choose_action(self, state, moves, pid):
            nonlocal latest, checkpoint_chosen
            snapshot = serialize_match_snapshot(state)
            latest = snapshot
            record = {
                "event": "decision", "tick": context["tick"], "pid": pid,
                "snapshot": snapshot, "legal_moves": moves,
                "config": {"difficulty": self.difficulty, "archetype": self.archetype,
                           "opponent_archetype": self.opponent_archetype},
                "agent_memory": list(self._main_pass_signature_counts.items()),
            }
            write(out / "last-snapshot.json", snapshot)
            emit({**record, "event": "decision_started"})
            decision = super().choose_action(state, moves, pid)
            record.update(action=matrix.complete_action(decision.action),
                          reasoning=decision.reasoning,
                          root_pure=snapshot == serialize_match_snapshot(state),
                          codec_matches=snapshot == serialize_match_snapshot(
                              deserialize_match_snapshot(snapshot)))
            emit(record)
            # Deterministic first post-pregame fallback, upgraded once at turn 3
            # or an earlier genuine mechanic continuation; never outcome selected.
            if not state.pregame_pending and not checkpoint_chosen:
                write(out / "restart-checkpoint.json", record)
                if state.turn >= 3 or any(m.get("type") == "choose_mechanic" for m in moves):
                    checkpoint_chosen = True
            return decision

    class ObservedRules(original_rules):
        def take_action(self, state, pid, action, **kwargs):
            nonlocal latest
            result = super().take_action(state, pid, action, **kwargs)
            if context.get("stage") == "apply_action":
                latest = serialize_match_snapshot(state)
                emit({"event": "applied", "tick": context["tick"], "pid": pid,
                      "action": action, "snapshot": latest,
                      "codec_matches": latest == serialize_match_snapshot(
                          deserialize_match_snapshot(latest))})
                write(out / "last-snapshot.json", latest)
            return result

    matrix.AIAgent, matrix.RulesEngine = ObservedAgent, ObservedRules
    try:
        result = matrix.run_game(decks[case["seat1"]]["deck"],
                                 decks[case["seat2"]]["deck"], case["seed"],
                                 policy["difficulty"], math.inf, observer=observer)
        result["status"] = "resolved" if result["winner"] is not None else "incomplete"
    except Exception as error:
        result = {"status": "soft_timeout" if isinstance(error, SoftDeadline) else "error",
                  "error": repr(error), "traceback": traceback.format_exc(),
                  "winner": None, "last_stage": context}
    finally:
        stream.close()
        matrix.AIAgent, matrix.RulesEngine = original_agent, original_rules
    result.update(case=case, wall_seconds=time.monotonic() - started)
    if latest is not None:
        write(out / "last-snapshot.json", latest)
    write(out / "result.json", result)


def schedule(policy):
    return [{"id": f"pair{index + 1}-seat{seat}-seed{seed}",
             "seat1": pair[0] if seat == 1 else pair[1],
             "seat2": pair[1] if seat == 1 else pair[0], "seed": seed}
            for index, pair in enumerate(policy["pairs"])
            for seat in (1, 2) for seed in policy["seeds"]]


def suite(evidence):
    policy = json.loads((evidence / "sample-policy.json").read_text())
    cases = schedule(policy)
    assert len(cases) == policy["games"] == 20
    write(evidence / "schedule.json", cases)
    receipts = []
    for case in cases:
        out = evidence / case["id"]
        out.mkdir(exist_ok=True)
        assert not (out / "process.json").exists(), "No sample reruns"
        command = [sys.executable, "-m", __name__, "game", str(evidence), canonical(case)]
        # __name__ is __main__ in CLI; use the module path explicitly.
        command[2] = "scripts.natural_ai_consumer_audit"
        with (out / "process.log").open("w") as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            print(canonical({"event": "game_started", "case": case, "pid": child.pid}), flush=True)
            try:
                code = child.wait(timeout=policy["game_hard_wall_seconds"])
                status = "exited"
            except subprocess.TimeoutExpired:
                child.kill()
                code = child.wait()
                status = "hard_timeout"
        receipt = {"case": case, "pid": child.pid, "exit_code": code, "status": status}
        write(out / "process.json", receipt)
        checkpoint = out / "restart-checkpoint.json"
        if checkpoint.exists():
            with (out / "restart-process.log").open("w") as log:
                restart = subprocess.Popen([sys.executable, "-m", "scripts.natural_ai_consumer_audit",
                                            "probe", str(checkpoint)], stdout=log, stderr=subprocess.STDOUT)
                try:
                    code = restart.wait(timeout=policy["restart_probe_hard_seconds"])
                    status = "exited"
                except subprocess.TimeoutExpired:
                    restart.kill()
                    code, status = restart.wait(), "hard_timeout"
            receipt["restart"] = {"pid": restart.pid, "exit_code": code, "status": status}
            write(out / "process.json", receipt)
        receipts.append(receipt)
        write(evidence / "suite-progress.json", receipts)
        print(canonical({"event": "game_terminal", **receipt}), flush=True)
    write(evidence / "suite-terminal.json", receipts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("suite", "game", "probe"))
    parser.add_argument("path", type=Path)
    parser.add_argument("case", nargs="?")
    args = parser.parse_args()
    os.umask(0o077)
    if args.mode == "suite":
        suite(args.path)
    elif args.mode == "game":
        game(args.path, json.loads(args.case))
    else:
        probe(args.path)
