from __future__ import annotations

import re


WARD_NUM_RE = re.compile(r"ward\s*[—-]?\s*\{?(\d+)\}?")


def ward_generic_tax(card) -> int:
    text = (getattr(card, "oracle_text", "") or "").lower()
    keywords = " ".join(str(k).lower() for k in (getattr(card, "keywords", []) or []))
    hay = f"{keywords} {text}"
    match = WARD_NUM_RE.search(hay)
    if not match:
        return 0
    try:
        return max(0, int(match.group(1)))
    except Exception:
        return 0


def ward_tax_for_targets(state, source_controller: int, target_ids: list[str]) -> int:
    total = 0
    for cid in target_ids:
        card = state.cards.get(cid)
        if not card:
            continue
        if card.controller == source_controller:
            continue
        total += ward_generic_tax(card)
    return total
