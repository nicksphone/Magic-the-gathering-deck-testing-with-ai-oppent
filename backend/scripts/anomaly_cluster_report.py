from __future__ import annotations

try:  # pragma: no cover - import path bootstrap for CLI execution
    from . import _bootstrap  # type: ignore[attr-defined]  # noqa: F401
except ImportError:  # pragma: no cover - direct script execution
    import _bootstrap  # noqa: F401
import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


PATTERNS = [
    ("land_miss", re.compile(r"plays? .+\.$", re.IGNORECASE)),
    ("cannot_pay", re.compile(r"cannot pay|cannot satisfy chosen costs|failed additional costs", re.IGNORECASE)),
    ("invalid_targets", re.compile(r"invalid targets", re.IGNORECASE)),
    ("stall_pass", re.compile(r"pass_priority", re.IGNORECASE)),
    ("ward_tax", re.compile(r"ward tax", re.IGNORECASE)),
    ("legend_rule", re.compile(r"legend rule", re.IGNORECASE)),
    ("x_value_error", re.compile(r"x value is required|x value must be non-negative", re.IGNORECASE)),
    ("stack_target", re.compile(r"target_stack_id|stack target", re.IGNORECASE)),
]


def classify(lines: list[str]) -> list[str]:
    labels: list[str] = []
    traces = [_parse_trace(line) for line in lines]
    traces = [t for t in traces if t is not None]
    text = "\n".join(lines)
    for name, pat in PATTERNS:
        if pat.search(text):
            labels.append(name)
    if _looks_like_main_phase_pass_loop(traces):
        labels.append("main_phase_pass_loop")
    if _looks_like_repeated_x_spell_error(lines):
        labels.append("x_spell_error_loop")
    if not labels:
        labels.append("other")
    return labels


def _parse_trace(line: str) -> dict | None:
    if not line.startswith("AI TRACE "):
        return None
    try:
        payload = json.loads(line[len("AI TRACE ") :])
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _looks_like_main_phase_pass_loop(traces: list[dict]) -> bool:
    count = 0
    for trace in traces:
        action = trace.get("action") or {}
        step = str(trace.get("step") or "").lower()
        if action.get("type") == "pass_priority" and "main" in step:
            count += 1
            if count >= 2:
                return True
    return False


def _looks_like_repeated_x_spell_error(lines: list[str]) -> bool:
    streak = 0
    for line in lines:
        low = line.lower()
        if "x value is required" in low or "x value must be non-negative" in low:
            streak += 1
            if streak >= 2:
                return True
        else:
            streak = 0
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to diagnostics jsonl")
    parser.add_argument("--out", default="anomaly-clusters.json", help="Output json report")
    args = parser.parse_args()

    clusters = Counter()
    samples = defaultdict(list)
    with Path(args.input).open("r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            row = json.loads(raw)
            labels = classify(row.get("log", []))
            key = "+".join(sorted(labels))
            clusters[key] += 1
            if len(samples[key]) < 3:
                samples[key].append(
                    {
                        "game": row.get("game"),
                        "winner": row.get("winner"),
                        "turns": row.get("turns"),
                        "life": row.get("life"),
                    }
                )

    out = {
        "total_games": sum(clusters.values()),
        "clusters": [
            {"label": k, "count": v, "samples": samples[k]}
            for k, v in clusters.most_common()
        ],
    }
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
