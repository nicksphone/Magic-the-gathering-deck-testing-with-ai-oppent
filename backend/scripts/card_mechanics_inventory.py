from __future__ import annotations

try:
    from . import _bootstrap
except ImportError:
    import _bootstrap

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from sqlmodel import Session

from persistence.db import engine, init_db
from persistence.repository import Repository

GAP_CANDIDATES = {"Annihilator", "Banding", "Craft", "Discover", "Dredge", "Escape", "Infect", "Manifest", "Morph", "Mutate", "Ninjutsu", "Prototype", "Suspend"}
CORE_HANDLERS = {"Annihilator", "Dredge", "Escape", "Infect", "Ninjutsu", "Prototype"}


def inventory(rows) -> dict:
    keywords, layouts, types = Counter(), Counter(), Counter()
    examples = defaultdict(list)
    cards = 0
    for row in rows:
        raw = json.loads(row.profiles_json).get("card_data")
        if not raw:
            continue
        cards += 1
        layouts[raw.get("layout", "unknown")] += 1
        for keyword in set(raw.get("keywords", [])):
            keywords[keyword] += 1
            if len(examples[keyword]) < 5:
                examples[keyword].append(raw["name"])
        type_lines = [face.get("type_line", "") for face in raw.get("card_faces", [])] or [raw.get("type_line", "")]
        card_types = set()
        for line in type_lines:
            card_types.update(line.split("\u2014", 1)[0].strip().split())
        for card_type in card_types:
            types[card_type] += 1
    return {
        "cards": cards,
        "keywords": dict(sorted(keywords.items())),
        "layouts": dict(sorted(layouts.items())),
        "type_and_supertype_counts": dict(sorted(types.items())),
        "gap_candidates": [{"keyword": keyword, "cards": keywords[keyword], "examples": examples[keyword], "status": "core_handler_added_integration_and_edge_cases_open" if keyword in CORE_HANDLERS else "needs_dedicated_rules_and_integration_validation"} for keyword in sorted(GAP_CANDIDATES) if keywords[keyword]],
        "rules_support_certified": False,
        "interpretation": "Inventory of canonical metadata, not engine certification. Some candidates now have dedicated core handlers, but complete interactions and HTTP/UI integration remain unverified. Reminder text may otherwise be partially inferred. Non-keyword mechanics need a separate Oracle-text and rules audit.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory canonical card types/layouts/keywords and rules gap candidates")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    init_db()
    with Session(engine) as session:
        report = inventory(Repository(session).list_card_knowledge())
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
