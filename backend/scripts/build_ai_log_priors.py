from __future__ import annotations

try:  # pragma: no cover - import path bootstrap for CLI execution
    from . import _bootstrap  # type: ignore[attr-defined]  # noqa: F401
except ImportError:  # pragma: no cover - direct script execution
    import _bootstrap  # noqa: F401
import json
from pathlib import Path

from sqlmodel import Session

from ai.log_priors import build_priors_from_examples, build_priors_from_logs, save_log_priors
from persistence.db import engine
from persistence.repository import Repository


def _read_training_run_logs(root: Path) -> list[list[str]]:
    out: list[list[str]] = []
    if not root.exists():
        return out
    for path in root.rglob("*.jsonl"):
        if "games" not in path.name and "all_games" not in path.name and "anomaly_games" not in path.name:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for raw in lines:
            raw = raw.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except Exception:
                continue
            log = row.get("log")
            if isinstance(log, list) and log:
                out.append([str(x) for x in log])
    return out


def _read_training_run_examples(root: Path) -> list[dict]:
    out: list[dict] = []
    if not root.exists():
        return out
    for path in root.rglob("*.jsonl"):
        if "training_examples" not in path.name and "examples" not in path.name:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for raw in lines:
            raw = raw.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except Exception:
                continue
            if isinstance(row, dict) and row.get("board_role_hint") and row.get("action_type"):
                out.append(row)
    return out


def main() -> None:
    logs: list[list[str]] = []
    with Session(engine) as session:
        repo = Repository(session)
        for match in repo.list_matches():
            try:
                decoded = json.loads(match.log_json)
            except Exception:
                continue
            if isinstance(decoded, list) and decoded:
                logs.append([str(x) for x in decoded])
    training_root = Path(__file__).resolve().parents[1] / "training_runs"
    logs.extend(_read_training_run_logs(training_root))
    payload = build_priors_from_logs(logs)
    examples = _read_training_run_examples(training_root)
    if examples:
        example_payload = build_priors_from_examples(examples)
        payload = _merge_priors(payload, example_payload)
    saved = save_log_priors(payload)
    print(
        json.dumps(
            {
                "generated_at": saved.get("generated_at"),
                "games": saved.get("samples", {}).get("games", 0),
                "logs": saved.get("samples", {}).get("logs", 0),
                "cards": len(saved.get("cards", {})),
            },
            indent=2,
        )
    )


def _merge_priors(primary: dict, secondary: dict) -> dict:
    merged = {
        "generated_at": None,
        "samples": {
            "games": int(primary.get("samples", {}).get("games", 0) or 0) + int(secondary.get("samples", {}).get("games", 0) or 0),
            "logs": int(primary.get("samples", {}).get("logs", 0) or 0) + int(secondary.get("samples", {}).get("logs", 0) or 0),
        },
        "cards": {},
    }
    cards = merged["cards"]
    for source in (primary.get("cards", {}), secondary.get("cards", {})):
        if not isinstance(source, dict):
            continue
        for name, row in source.items():
            if not isinstance(row, dict):
                continue
            existing = cards.get(name)
            if not isinstance(existing, dict):
                cards[name] = dict(row)
                continue
            cards[name] = _merge_card_rows(existing, row)
    return merged


def _merge_card_rows(left: dict, right: dict) -> dict:
    merged = dict(left)
    left_casts = int(left.get("casts", 0) or 0)
    right_casts = int(right.get("casts", 0) or 0)
    total_casts = left_casts + right_casts
    if total_casts <= 0:
        return merged
    merged["casts"] = total_casts
    left_seen = int(left.get("seen_in_logs", 0) or 0)
    right_seen = int(right.get("seen_in_logs", 0) or 0)
    merged["seen_in_logs"] = left_seen + right_seen
    merged["avg_turn"] = round(
        ((float(left.get("avg_turn", 0.0) or 0.0) * left_casts) + (float(right.get("avg_turn", 0.0) or 0.0) * right_casts)) / total_casts,
        3,
    )
    for key in ("early_turn_cast_rate", "mid_turn_cast_rate", "late_turn_cast_rate"):
        merged[key] = round(
            ((float(left.get(key, 0.0) or 0.0) * left_casts) + (float(right.get(key, 0.0) or 0.0) * right_casts)) / total_casts,
            3,
        )
    merged["preferred_min_turn"] = max(1, int(round(merged["avg_turn"] - 1.0)))
    merged_roles = dict(left.get("board_roles", {}) or {})
    for role, row in (right.get("board_roles", {}) or {}).items():
        if role not in merged_roles:
            merged_roles[role] = dict(row)
            continue
        existing = merged_roles[role]
        existing_casts = int(existing.get("casts", 0) or 0)
        row_casts = int(row.get("casts", 0) or 0)
        role_casts = existing_casts + row_casts
        if role_casts <= 0:
            continue
        existing_avg = float(existing.get("avg_turn", 0.0) or 0.0)
        row_avg = float(row.get("avg_turn", 0.0) or 0.0)
        existing["casts"] = role_casts
        existing["avg_turn"] = round(
            ((existing_avg * existing_casts) + (row_avg * row_casts)) / role_casts,
            3,
        )
        for key in ("early_turn_cast_rate", "mid_turn_cast_rate", "late_turn_cast_rate"):
            existing[key] = round(
                ((float(existing.get(key, 0.0) or 0.0) * existing_casts) + (float(row.get(key, 0.0) or 0.0) * row_casts)) / role_casts,
                3,
            )
        existing["preferred_min_turn"] = max(1, int(round(existing["avg_turn"] - 1.0)))
    merged["board_roles"] = merged_roles
    return merged


if __name__ == "__main__":
    main()
