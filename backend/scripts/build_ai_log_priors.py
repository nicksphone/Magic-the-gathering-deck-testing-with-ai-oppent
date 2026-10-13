from __future__ import annotations

try:  # pragma: no cover - import path bootstrap for CLI execution
    from . import _bootstrap  # type: ignore[attr-defined]  # noqa: F401
except ImportError:  # pragma: no cover - direct script execution
    import _bootstrap  # noqa: F401
import json
import argparse
from collections import Counter
from copy import deepcopy
from pathlib import Path

from ai.log_priors import (_cast_context, _opponent_archetype, build_priors_from_examples,
                           build_priors_from_logs, save_log_priors)


def _training_records(root: Path, *, examples: bool):
    if not root.exists():
        return
    for path in sorted(root.rglob("*.jsonl")):
        if not any(name in path.name for name in (("training_examples", "examples") if examples else ("games",))):
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
            if isinstance(row, dict):
                yield path, row


def _read_training_run_logs(root: Path) -> list[list[str]]:
    return [[str(item) for item in row["log"]] for _, row in _training_records(root, examples=False)
            if isinstance(row.get("log"), list) and row["log"]]


def _read_training_run_examples(root: Path) -> list[dict]:
    return [row for _, row in _training_records(root, examples=True)
            if row.get("board_role_hint") and row.get("action_type")]


def _qualified_export_contexts(root: Path) -> tuple[dict, dict]:
    """Require explicit game/action provenance; never invent execution IDs."""
    import math
    candidates: dict[tuple, list[dict]] = {}
    unavailable = Counter()

    def record(path, row):
        context = _opponent_archetype(row)
        if context is None:
            unavailable["unknown_or_missing_context"] += 1
            return
        game, index = row.get("game"), row.get("action_index")
        if (type(game) not in (str, int) or game == "" or type(index) is not int or index < 0
                or type(row.get("pid")) is not int or row["pid"] not in (1, 2)
                or type(row.get("turn")) is not int or row["turn"] < 1):
            unavailable["missing_action_provenance"] += 1
            return
        try:
            math.isfinite(row["turn"])
        except OverflowError:
            unavailable["invalid_context_turn"] += 1
            return
        key = (str(path.parent.relative_to(root)), type(game).__name__, game, index)
        value = {"pid": row["pid"], "turn": row["turn"], "action_type": row["action_type"],
                 "action_card_name": row["action_card_name"].strip().lower(),
                 "opponent_archetype": context}
        candidates.setdefault(key, []).append(value)

    for path, game in _training_records(root, examples=False):
        pending = None
        for line in game.get("log", []) if isinstance(game.get("log"), list) else []:
            if not isinstance(line, str):
                continue
            if "AI TRACE " in line:
                pending = None
                try:
                    parsed = json.loads(line.split("AI TRACE ", 1)[1])
                    if isinstance(parsed, dict):
                        pending = parsed
                except (ValueError, IndexError):
                    pass
            elif " casts/activates " in line:
                actor, name = line.split(" casts/activates ", 1)
                name = name.strip().rstrip(".")
                context = _cast_context(pending, actor.strip(), name)
                if context is not None:
                    record(path, {"game": game.get("game"), "action_index": pending.get("action_index"),
                                  "pid": pending.get("pid"), "turn": pending.get("turn"),
                                  "action_type": pending["action"]["type"], "action_card_name": name,
                                  "opponent_archetype": context})
                else:
                    unavailable["unassociated_or_unknown_log_context"] += 1
                pending = None
    for path, row in _training_records(root, examples=True):
        if (isinstance(row.get("action_type"), str) and row["action_type"]
                and isinstance(row.get("action_card_name"), str) and row["action_card_name"].strip()):
            record(path, row)
    rows = []
    for values in candidates.values():
        if any(value != values[0] for value in values[1:]):
            unavailable["conflicting_action_provenance"] += len(values)
        elif values[0]["action_type"] in {"cast_spell", "activate_ability"}:
            rows.append(values[0])
    return build_priors_from_examples(rows), dict(sorted(unavailable.items()))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build replay timing priors")
    parser.add_argument("--training-root", type=Path, help="Explicit exports-only mode; never opens SQL")
    args = parser.parse_args(argv)
    training_root = args.training_root or Path(__file__).resolve().parents[1] / "training_runs"
    logs: list[list[str]] = []
    if args.training_root is None:
        # Preserve the legacy CLI; SQL is absent from imports and explicit offline runs.
        from sqlmodel import Session
        from persistence.db import engine
        from persistence.repository import Repository
        with Session(engine) as session:
            repo = Repository(session)
            for match in repo.list_matches():
                try:
                    decoded = json.loads(match.log_json)
                except Exception:
                    continue
                if isinstance(decoded, list) and decoded:
                    logs.append([str(item) for item in decoded])
    logs.extend(_read_training_run_logs(training_root))
    payload = build_priors_from_logs(logs)
    examples = _read_training_run_examples(training_root)
    if examples:
        example_payload = build_priors_from_examples(examples)
        payload = _merge_priors(payload, example_payload)
    context_payload, unavailable = _qualified_export_contexts(training_root)
    for name, row in payload["cards"].items():
        row.pop("opponent_archetypes", None)
        contexts = context_payload["cards"].get(name, {}).get("opponent_archetypes")
        if contexts:
            row["opponent_archetypes"] = contexts
    context_available = any(row.get("opponent_archetypes") for row in payload["cards"].values())
    if args.training_root is not None and not context_available:
        print(json.dumps({"context_available": False, "context_unavailable": unavailable,
                          "games": payload["samples"]["games"], "logs": payload["samples"]["logs"],
                          "cards": len(payload["cards"]), "saved": False,
                          "reason": "No qualified two-archetype timing rows; Task 3.3 data gap"}, indent=2))
        return
    saved = save_log_priors(payload)
    print(
        json.dumps(
            {
                "generated_at": saved.get("generated_at"),
                "games": saved.get("samples", {}).get("games", 0),
                "logs": saved.get("samples", {}).get("logs", 0),
                "cards": len(saved.get("cards", {})),
                "context_available": context_available,
                "context_unavailable": unavailable,
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
                cards[name] = deepcopy(row)
                continue
            cards[name] = _merge_card_rows(existing, row)
    return merged


def _merge_card_rows(left: dict, right: dict) -> dict:
    merged = deepcopy(left)
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
    merged_roles = deepcopy(left.get("board_roles", {}) or {})
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
    contexts = deepcopy(left.get("opponent_archetypes", {}) or {})
    for context, row in sorted((right.get("opponent_archetypes", {}) or {}).items()):
        contexts[context] = _merge_card_rows(contexts[context], row) if context in contexts else deepcopy(row)
        contexts[context].pop("board_roles", None)
        contexts[context].pop("seen_in_logs", None)
    if contexts:
        merged["opponent_archetypes"] = dict(sorted(contexts.items()))
    return merged


if __name__ == "__main__":
    main()
