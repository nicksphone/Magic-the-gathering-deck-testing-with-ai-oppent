from __future__ import annotations

import re

from game_state.state import Zone

PT_STATIC_RE = re.compile(
    r"\b(other\s+)?(creature tokens|artifact creatures|[a-z]+ creatures|creatures|[a-z]+s?)\s+"
    r"(you control|your opponents control)\s+get\s+([+-]\d+)\/([+-]\d+)"
)
PT_SET_RE = re.compile(
    r"\bbase power and toughness\s+(\d+)\/(\d+)\b"
)
KW_STATIC_RE = re.compile(
    r"\b(other\s+)?(creature tokens|artifact creatures|[a-z]+ creatures|creatures|[a-z]+s?)\s+"
    r"(you control|your opponents control)\s+(?:have|has)\s+([^.]*)"
)
KNOWN_KEYWORDS = [
    "trample",
    "first strike",
    "double strike",
    "haste",
    "flash",
    "lifelink",
    "deathtouch",
    "flying",
    "reach",
    "menace",
    "vigilance",
    "defender",
    "indestructible",
    "hexproof",
    "islandwalk",
    "swampwalk",
    "mountainwalk",
    "forestwalk",
    "plainswalk",
]


def effective_power(state, card_id: str) -> int:
    card = state.cards[card_id]
    base_p, _ = _base_pt_with_layers(state, card_id)
    base = int(base_p or 0)
    p_bonus, _ = _continuous_pt_delta(state, card_id)
    counter_bonus = _counter_pt_delta(card)
    return base + p_bonus + counter_bonus


def effective_toughness(state, card_id: str) -> int:
    card = state.cards[card_id]
    _, base_t = _base_pt_with_layers(state, card_id)
    base = int(base_t or 0)
    _, t_bonus = _continuous_pt_delta(state, card_id)
    counter_bonus = _counter_pt_delta(card)
    return base + t_bonus + counter_bonus


def _counter_pt_delta(card) -> int:
    """Return PT bonus from +1/+1 and -1/-1 counters on a card."""
    bonus = 0
    for counter, amount in (getattr(card, "counters", {}) or {}).items():
        if counter == "+1/+1":
            bonus += int(amount)
        elif counter == "-1/-1":
            bonus -= int(amount)
    return bonus


def effective_keywords(state, card_id: str) -> list[str]:
    card = state.cards[card_id]
    out = {str(k).lower() for k in (card.keywords or [])}
    if not _is_battlefield(card):
        return sorted(out)
    if "Creature" not in card.types:
        return sorted(out)
    for src_id in _all_battlefield_ids(state):
        src = state.cards.get(src_id)
        if not src:
            continue
        for scope, other_only, subject, granted in _iter_keyword_grants(src):
            if _scope_controller(src.controller, scope, card.controller):
                if other_only and src_id == card_id:
                    continue
                if _subject_matches(state, card_id, subject):
                    out.update(granted)
    return sorted(out)


def has_keyword(state, card_id: str, keyword: str) -> bool:
    k = (keyword or "").lower()
    return k in set(effective_keywords(state, card_id))


def _base_pt_with_layers(state, card_id: str) -> tuple[int | None, int | None]:
    card = state.cards[card_id]
    base_p = card.power
    base_t = card.toughness
    # Minimal layer support: base PT setters from static text.
    for src_id in _all_battlefield_ids(state):
        src = state.cards.get(src_id)
        if not src:
            continue
        text = (getattr(src, "oracle_text", "") or "").lower()
        if "creatures you control have base power and toughness" in text:
            if src.controller != card.controller or "Creature" not in card.types:
                continue
            m = PT_SET_RE.search(text)
            if m:
                base_p = int(m.group(1))
                base_t = int(m.group(2))
        elif src_id == card_id:
            m = PT_SET_RE.search(text)
            if m:
                base_p = int(m.group(1))
                base_t = int(m.group(2))
    return base_p, base_t


def _continuous_pt_delta(state, card_id: str) -> tuple[int, int]:
    card = state.cards[card_id]
    if not _is_battlefield(card):
        return (0, 0)
    if "Creature" not in card.types:
        return (0, 0)
    p_bonus = 0
    t_bonus = 0
    for src_id in _all_battlefield_ids(state):
        src = state.cards.get(src_id)
        if not src:
            continue
        for scope, other_only, subject, p_delta, t_delta in _iter_pt_modifiers(src):
            if not _scope_controller(src.controller, scope, card.controller):
                continue
            if other_only and src_id == card_id:
                continue
            if not _subject_matches(state, card_id, subject):
                continue
            p_bonus += p_delta
            t_bonus += t_delta
    return p_bonus, t_bonus


def _iter_pt_modifiers(source_card):
    text = (getattr(source_card, "oracle_text", "") or "").lower()
    for match in PT_STATIC_RE.finditer(text):
        other_only = bool(match.group(1))
        subject = match.group(2).strip()
        scope = match.group(3).strip()
        p_delta = int(match.group(4))
        t_delta = int(match.group(5))
        yield (scope, other_only, subject, p_delta, t_delta)


def _iter_keyword_grants(source_card):
    text = (getattr(source_card, "oracle_text", "") or "").lower()
    for match in KW_STATIC_RE.finditer(text):
        other_only = bool(match.group(1))
        subject = match.group(2).strip()
        scope = match.group(3).strip()
        granted_text = match.group(4).strip()
        granted = [kw for kw in KNOWN_KEYWORDS if kw in granted_text]
        if granted:
            yield (scope, other_only, subject, granted)


def _scope_controller(source_controller: int, scope: str, target_controller: int) -> bool:
    if scope == "you control":
        return source_controller == target_controller
    if scope == "your opponents control":
        return source_controller != target_controller
    return False


def _subject_matches(state, card_id: str, subject: str) -> bool:
    card = state.cards[card_id]
    s = (subject or "").strip().lower()
    if s == "creatures":
        return "Creature" in card.types
    if s == "creature tokens":
        return "Creature" in card.types and "Token" in card.types
    if s == "artifact creatures":
        return "Creature" in card.types and "Artifact" in card.types
    # "elf creatures"
    if s.endswith(" creatures"):
        tribe = s.replace(" creatures", "").strip()
        return _has_subtype(card, tribe)
    # "elves", "goblins", etc.
    if s.endswith("ves"):
        singular = f"{s[:-3]}f"
    elif s.endswith("ies"):
        singular = f"{s[:-3]}y"
    elif s.endswith("s"):
        singular = s[:-1]
    else:
        singular = s
    return _has_subtype(card, singular)


def _has_subtype(card, subtype: str) -> bool:
    if "Creature" not in (getattr(card, "types", []) or []):
        return False
    type_line = (getattr(card, "type_line", "") or "").lower()
    if "—" in type_line:
        right = type_line.split("—", 1)[1]
    elif "-" in type_line:
        right = type_line.split("-", 1)[1]
    else:
        right = ""
    tokens = [t.strip(" ,.") for t in right.split()]
    candidates = {subtype.lower(), f"{subtype.lower()}s"}
    if subtype.lower().endswith("f"):
        candidates.add(f"{subtype.lower()[:-1]}ves")
    if subtype.lower().endswith("fe"):
        candidates.add(f"{subtype.lower()[:-2]}ves")
    return any(tok in candidates for tok in tokens)


def _all_battlefield_ids(state) -> list[str]:
    ids: list[str] = []
    for pid in state.players:
        ids.extend(list(state.players[pid].battlefield))
    return ids


def _is_battlefield(card) -> bool:
    return getattr(card, "zone", None) == Zone.BATTLEFIELD
