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
from typing import Any

from sqlmodel import Session

from card_data.hydration import hydrate_deck_cards, ready_for_match
from decks.builtin_decks import BUILTIN_DECKS
from decks.expansion_top_decks import EXPANSION_TOP_DECKS
from game_state.state import MatchFactory
from persistence.db import engine, init_db
from persistence.repository import Repository
from rules_engine.ability_model import build_ability_spec


DECK_LINE = re.compile(r"^\s*(\d+)\s*x?\s+(.+?)\s*$", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect local hydration and parser paths in the shipped deck corpus")
    parser.add_argument("--out", default="", help="Optional JSON output path")
    return parser.parse_args()


def collect_corpus() -> dict[str, dict[str, Any]]:
    corpus: dict[str, dict[str, Any]] = {}

    def add_deck(deck_name: str, source: str, deck_text: str) -> None:
        for raw_line in deck_text.splitlines():
            match = DECK_LINE.match(raw_line.strip())
            if not match:
                continue
            quantity = int(match.group(1))
            name = match.group(2).strip()
            key = name.lower()
            row = corpus.setdefault(key, {"name": name, "copies": 0, "decks": [], "sources": []})
            row["copies"] += quantity
            if deck_name not in row["decks"]:
                row["decks"].append(deck_name)
            if source not in row["sources"]:
                row["sources"].append(source)

    for deck_name, deck_text in BUILTIN_DECKS.items():
        add_deck(deck_name, "builtin", deck_text)
    for entry in EXPANSION_TOP_DECKS:
        add_deck(entry["deck_name"], str(entry["code"]), entry["deck_text"])
    return corpus


def _family_for(text: str) -> str:
    oracle = (text or "").lower()
    families = (
        ("modal", ("choose one", "choose two")),
        ("replacement_or_prevention", ("instead", "can't be prevented", "cannot be prevented")),
        ("conditional_target", ("mana value", "nonartifact", "nonland", "noncreature", "if it has")),
        ("triggered_ability", ("when ", "whenever ", "at the beginning")),
        ("continuous_effect", ("get +", "have ", "as long as", "power is equal")),
        ("transform_or_face", ("transform", "daybound", "nightbound")),
        ("alternate_or_temporary_cost", ("adventure", "without paying", "may play those cards")),
        ("counter_or_copied_object", ("counter target", "copy target")),
        ("attachment", ("enchant ", "equip ", "attach")),
    )
    for family, terms in families:
        if any(term in oracle for term in terms):
            return family
    return "other_oracle"


def analyze_corpus(repo=None) -> dict[str, Any]:
    if repo is None:
        init_db()
        with Session(engine) as session:
            return analyze_corpus(Repository(session))
    corpus = collect_corpus()
    entries = [{"quantity": 1, "card_name": row["name"]} for row in corpus.values()]
    hydrated = hydrate_deck_cards(repo, entries)
    metadata = {item["card_name"].casefold(): item for item in hydrated}
    cached = repo.get_cached_cards_by_names([item["card_name"] for item in entries])
    if hydrated:
        blank_deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
        state = MatchFactory.from_decks(hydrated, blank_deck, seed=101)
        runtime_cards = {card.name.casefold(): card for card in state.cards.values() if card.owner == 1}
        status_counts: Counter[str] = Counter()
        weighted_counts: Counter[str] = Counter()
        family_counts: Counter[str] = Counter()
        family_weighted: Counter[str] = Counter()
        cards: list[dict[str, Any]] = []
        for row in sorted(corpus.values(), key=lambda item: str(item["name"]).lower()):
            name = str(row["name"])
            item = metadata[name.casefold()]
            card = runtime_cards[name.casefold()]
            oracle = card.oracle_text
            sources = item.get("card_data_sources", [])
            cache_row = cached.get(name.casefold())
            spec = build_ability_spec(state, card, 1)
            if not oracle.strip() and not sources:
                status = "missing_oracle"
            elif not ready_for_match(item):
                status = "incomplete_card_data"
            elif spec.unsupported_resolution:
                status = "unsupported_resolution"
            elif spec.effect.key == "noop" and spec.modes:
                status = "choice_pending"
            elif spec.event_supported:
                status = "structured_event"
            elif spec.used_fallback:
                status = "parser_fallback"
            elif spec.effect.key == "noop":
                status = "static_or_noop"
            else:
                status = "structured_effect"
            family = _family_for(oracle)
            status_counts[status] += 1
            weighted_counts[status] += int(row["copies"])
            if status in {"parser_fallback", "missing_oracle", "incomplete_card_data", "unsupported_resolution"}:
                family_counts[family] += 1
                family_weighted[family] += int(row["copies"])
            cards.append(
                {
                    **row,
                    "cached": name.casefold() in cached,
                    "oracle_source": ("cache" if cache_row and getattr(cache_row, "oracle_text", "")
                                      else "local_knowledge" if "local_knowledge" in sources
                                      else "offline_seed" if "offline_seed" in sources else "missing"),
                    "card_data_sources": sources,
                    "ready_for_match": ready_for_match(item),
                    "semantics_verified": False,
                    "faces": [{"name": face.get("name"), "type_line": face.get("type_line"),
                               "colors": face.get("colors"), "semantics_verified": False}
                              for face in card.card_faces],
                    "unsupported_resolution": list(spec.unsupported_resolution),
                    "choices": spec.choices,
                    "modes": spec.modes,
                    "status": status,
                    "family": family,
                    "effect_key": spec.effect.key,
                    "oracle_preview": " ".join(oracle.split())[:240],
                }
            )

    else:
        cards = []
        status_counts, weighted_counts, family_counts, family_weighted = (Counter() for _ in range(4))
    unresolved = [card for card in cards if card["status"] in {
        "parser_fallback", "missing_oracle", "incomplete_card_data", "unsupported_resolution"}]
    unresolved.sort(key=lambda card: (-int(card["copies"]), str(card["name"]).lower()))
    return {
        "scope": {
            "semantics_verified": False,
            "legal_actions_evaluated": False,
            "purpose": "hydration and parser diagnostics, not gameplay certification",
            "face_evaluation": "default face compiled; alternate faces listed, not separately compiled",
            "parser_fallback_means_unsupported": False,
        },
        "corpus": {
            "unique_cards": len(cards),
            "total_copies": sum(int(card["copies"]) for card in cards),
            "builtin_decks": len(BUILTIN_DECKS),
            "expansion_decks": len(EXPANSION_TOP_DECKS),
        },
        "status_unique": dict(status_counts),
        "status_weighted": dict(weighted_counts),
        "unresolved_families_unique": dict(family_counts.most_common()),
        "unresolved_families_weighted": dict(family_weighted.most_common()),
        "highest_impact_unresolved": unresolved[:25],
        "cards": cards,
    }


def main() -> int:
    args = parse_args()
    report = analyze_corpus()
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": args.out or "stdout",
                "corpus": report["corpus"],
                "status_weighted": report["status_weighted"],
                "unresolved_families_weighted": report["unresolved_families_weighted"],
            },
            indent=2,
        )
    )
    if not args.out:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
