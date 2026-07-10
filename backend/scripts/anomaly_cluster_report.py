from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


PATTERNS = [
    ("land_miss", re.compile(r"plays? [A-Za-z]+\.$", re.IGNORECASE)),
    ("cannot_pay", re.compile(r"cannot pay", re.IGNORECASE)),
    ("invalid_targets", re.compile(r"invalid targets", re.IGNORECASE)),
    ("stall_pass", re.compile(r"pass_priority", re.IGNORECASE)),
    ("ward_tax", re.compile(r"ward tax", re.IGNORECASE)),
    ("legend_rule", re.compile(r"legend rule", re.IGNORECASE)),
]


def classify(lines: list[str]) -> list[str]:
    labels: list[str] = []
    text = "\n".join(lines)
    for name, pat in PATTERNS:
        if pat.search(text):
            labels.append(name)
    if not labels:
        labels.append("other")
    return labels


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
