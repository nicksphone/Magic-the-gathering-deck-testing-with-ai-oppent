from __future__ import annotations

try:  # pragma: no cover - import path bootstrap for CLI execution
    from . import _bootstrap  # type: ignore[attr-defined]  # noqa: F401
except ImportError:  # pragma: no cover - direct script execution
    import _bootstrap  # noqa: F401
import argparse
import json
import subprocess
import sys
from pathlib import Path

from decks.bootstrap import ensure_builtin_decks, ensure_expansion_top_decks
from persistence.db import engine, init_db
from persistence.repository import Repository
from sqlmodel import Session


def run_cmd(cmd: list[str]) -> dict:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {"code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    p = argparse.ArgumentParser(description="Fail CI on timeout/pass-overuse/determinism regression")
    p.add_argument("--output-dir", default="training_runs/ci_gate")
    p.add_argument("--matches-per-pair", type=int, default=1)
    p.add_argument("--max-ticks", type=int, default=6000)
    p.add_argument("--difficulty", default="master")
    p.add_argument("--max-decks", type=int, default=10)
    p.add_argument("--max-timeouts", type=int, default=0)
    p.add_argument("--max-determinism-failures", type=int, default=0)
    p.add_argument("--max-passed-with-options", type=int, default=500)
    args = p.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rr_out = out_dir / "overnight_summary.json"
    replay_out = out_dir / "regression_matrix_replay.json"

    init_db()
    with Session(engine) as session:
        repo = Repository(session)
        ensure_builtin_decks(repo)
        ensure_expansion_top_decks(repo)

    rr = run_cmd(
        [
            sys.executable,
            "scripts/overnight_verbose_round_robin.py",
            "--matches-per-pair",
            str(args.matches_per_pair),
            "--difficulty",
            args.difficulty,
            "--max-ticks",
            str(args.max_ticks),
            "--max-decks",
            str(args.max_decks),
            "--sources",
            "builtin,user",
            "--output-dir",
            str(out_dir),
        ]
    )
    if rr["code"] != 0:
        print(rr["stdout"])
        print(rr["stderr"], file=sys.stderr)
        return rr["code"]

    # find latest overnight summary in output dir
    summaries = sorted(out_dir.glob("overnight-*/summary.json"))
    if not summaries:
        print("No overnight summary produced", file=sys.stderr)
        return 2
    rr_summary = load_json(summaries[-1])
    rr_out.write_text(json.dumps(rr_summary, indent=2), encoding="utf-8")

    replay = run_cmd(
        [
            sys.executable,
            "scripts/regression_matrix_replay.py",
            "--matches-per-pair",
            str(args.matches_per_pair),
            "--difficulty",
            args.difficulty,
            "--max-ticks",
            str(args.max_ticks),
            "--max-decks",
            str(args.max_decks),
            "--output",
            str(replay_out),
        ]
    )
    if replay["code"] != 0:
        print(replay["stdout"])
        print(replay["stderr"], file=sys.stderr)
        return replay["code"]
    replay_summary = load_json(replay_out)

    totals = rr_summary.get("totals", {})
    timeouts = int(totals.get("timeouts", 0))
    long_game_timeouts = int(totals.get("long_game_timeouts", 0))
    passed = int(totals.get("passed_with_options", 0))
    det_fail = int(replay_summary.get("determinism_failures", 0))

    failed = False
    if timeouts > args.max_timeouts:
        print(f"FAIL: timeouts {timeouts} > {args.max_timeouts}")
        failed = True
    if passed > args.max_passed_with_options:
        print(f"FAIL: passed_with_options {passed} > {args.max_passed_with_options}")
        failed = True
    if det_fail > args.max_determinism_failures:
        print(f"FAIL: determinism_failures {det_fail} > {args.max_determinism_failures}")
        failed = True

    print(
        json.dumps(
                {
                    "timeouts": timeouts,
                    "long_game_timeouts": long_game_timeouts,
                    "passed_with_options": passed,
                    "determinism_failures": det_fail,
                "overnight_summary": str(rr_out),
                "replay_summary": str(replay_out),
                "status": "fail" if failed else "pass",
            },
            indent=2,
        )
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
