from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from scripts import ci_regression_gate


def test_ci_gate_round_robin_command_always_requests_complete_games_log() -> None:
    args = SimpleNamespace(matches_per_pair=2, difficulty="master", max_ticks=100, max_decks=6)

    assert hasattr(ci_regression_gate, "build_round_robin_command")
    command = ci_regression_gate.build_round_robin_command(args, Path("gate-output"))  # type: ignore[attr-defined]

    assert "--write-full-log-for-all-games" in command
    assert command[command.index("--output-dir") + 1] == "gate-output"


def test_ci_gate_has_explicit_out_summary_path_separate_from_output_directory() -> None:
    assert hasattr(ci_regression_gate, "parse_args")
    args = ci_regression_gate.parse_args(  # type: ignore[attr-defined]
        ["--output-dir", "gate-artifacts", "--out", "/tmp/kb-baseline-gate.json"]
    )

    assert args.output_dir == "gate-artifacts"
    assert args.out == "/tmp/kb-baseline-gate.json"
    assert ci_regression_gate.summary_output_path(args, Path(args.output_dir)) == Path(  # type: ignore[attr-defined]
        "/tmp/kb-baseline-gate.json"
    )
