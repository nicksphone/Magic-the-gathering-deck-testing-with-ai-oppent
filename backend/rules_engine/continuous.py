from __future__ import annotations

import re
from typing import Any

from game_state.state import Zone

PT_STATIC_RE = re.compile(
    r"\b(other\s+)?(creature tokens|artifact creatures|[a-z]+ creatures|creatures|[a-z]+s?)\s+"
    r"(you control|your opponents control)\s+get\s+([+-]\d+)\/([+-]\d+)"
)
PT_SET_RE = re.compile(
    r"\b(?:base power and toughness\s+(\d+)\/(\d+)|(?:are|become|becomes|is)\s+(\d+)\/(\d+)|set(?:s)?(?:\s+their)?\s+base power and toughness\s+(\d+)\/(\d+))\b"
)
PT_SET_SCOPE_RE = re.compile(
    r"\b(other\s+)?(creature tokens|artifact creatures|[a-z]+ creatures|creatures|[a-z]+s?)\s+"
    r"(you control|your opponents control)\s+"
    r"(?:base power and toughness\s+(\d+)\/(\d+)|(?:are|become|becomes|is)\s+(\d+)\/(\d+)|"
    r"set(?:s)?(?:\s+their)?\s+base power and toughness\s+(\d+)\/(\d+))\b"
)
SELF_SCALE_GRAVE_RE = re.compile(
    r"\bgets\s+([+-]\d+)\/([+-]\d+)\s+for each\s+([a-z\s]+?)\s+card[s]?\s+in\s+(your|all)\s+graveyard[s]?\b"
)
SELF_SCALE_BF_RE = re.compile(
    r"\bgets\s+([+-]\d+)\/([+-]\d+)\s+for each\s+(other\s+)?([a-z\s]+?)\s+you control\b"
)
CARD_TYPE_COUNT_RE = re.compile(r"number of card types among cards in all graveyards", re.IGNORECASE)
KW_STATIC_RE = re.compile(
    r"\b(other\s+)?(creature tokens|artifact creatures|[a-z]+ creatures|creatures|[a-z]+s?)\s+"
    r"(you control|your opponents control)\s+(?:have|has)\s+([^.]*)"
)
PT_AND_KW_STATIC_RE = re.compile(
    r"\b(other\s+)?(creature tokens|artifact creatures|[a-z]+ creatures|creatures|[a-z]+s?)\s+"
    r"(you control|your opponents control)\s+get\s+[+-]\d+\/[+-]\d+\s+and\s+(?:have|has)\s+([^.]*)"
)
KW_REMOVE_RE = re.compile(
    r"\b(other\s+)?(creature tokens|artifact creatures|[a-z]+ creatures|creatures|[a-z]+s?)\s+"
    r"(you control|your opponents control)\s+(?:lose|loses)\s+([^.]*)"
)
KW_CANT_HAVE_RE = re.compile(
    r"\b(other\s+)?(creature tokens|artifact creatures|[a-z]+ creatures|creatures|[a-z]+s?)\s+"
    r"(you control|your opponents control)\s+can't have\s+([^.]*)"
)
PT_AND_KW_REMOVE_RE = re.compile(
    r"\b(other\s+)?(creature tokens|artifact creatures|[a-z]+ creatures|creatures|[a-z]+s?)\s+"
    r"(you control|your opponents control)\s+get\s+[+-]\d+\/[+-]\d+\s+and\s+(?:lose|loses)\s+([^.]*)"
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
    "shroud",
    "shadow",
    "fear",
    "intimidate",
    "islandwalk",
    "swampwalk",
    "mountainwalk",
    "forestwalk",
    "plainswalk",
    "nonbasic landwalk",
    "snow landwalk",
    "desertwalk",
    "wasteswalk",
    "legendary landwalk",
]


def effect_timestamp(card) -> int:
    """Return the persisted timestamp used by layer and replacement ordering."""
    explicit = int(getattr(card, "effect_timestamp", 0) or 0)
    return explicit or int(getattr(card, "static_order", 0) or 0)


def _continuous_layer_sort_key(state, source_id: str, layer: str) -> tuple[int, int, int, int, int, str]:
    """Order supported continuous effects by rules layer, then timestamp.

    Keyword changes are layer 6; base P/T setters and modifiers are 7b/7c.
    The remaining fields keep same-layer, same-timestamp fixtures deterministic.
    """
    if layer.startswith("keyword-"):
        layer_rank = 6
        sublayer = 0
    elif layer == "pt-set":
        layer_rank = 7
        sublayer = 0
    elif layer.startswith("pt-mod:"):
        layer_rank = 7
        sublayer = 1
    else:
        layer_rank = 7
        sublayer = 2
    source = state.cards.get(source_id)
    position = _battlefield_position_map(state).get(source_id, 0)
    return (
        layer_rank,
        sublayer,
        effect_timestamp(source),
        int(getattr(source, "entered_turn", 0) or 0),
        position,
        str(source_id),
    )


def effective_power(state, card_id: str) -> int:
    card = state.cards[card_id]
    base_p, _ = _base_pt_with_layers(state, card_id)
    base = int(base_p or 0)
    p_bonus, _ = _continuous_pt_delta(state, card_id)
    counter_bonus = _counter_pt_delta(card)
    temp_bonus = int((getattr(card, "counters", {}) or {}).get("__eot_power", 0))
    return base + p_bonus + counter_bonus + temp_bonus


def effective_toughness(state, card_id: str) -> int:
    card = state.cards[card_id]
    _, base_t = _base_pt_with_layers(state, card_id)
    base = int(base_t or 0)
    _, t_bonus = _continuous_pt_delta(state, card_id)
    counter_bonus = _counter_pt_delta(card)
    temp_bonus = int((getattr(card, "counters", {}) or {}).get("__eot_toughness", 0))
    return base + t_bonus + counter_bonus + temp_bonus


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
    out = {str(k).lower() for k in (getattr(card, "keywords", None) or [])}
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
        for scope, other_only, subject, removed in _iter_keyword_removals(src):
            if _scope_controller(src.controller, scope, card.controller):
                if other_only and src_id == card_id:
                    continue
                if _subject_matches(state, card_id, subject):
                    if "all abilities" in removed:
                        out.clear()
                    else:
                        out.difference_update(removed)
    return sorted(out)


def has_keyword(state, card_id: str, keyword: str) -> bool:
    k = (keyword or "").lower()
    return k in set(effective_keywords(state, card_id))


def _base_pt_with_layers(state, card_id: str) -> tuple[int | None, int | None]:
    card = state.cards[card_id]
    base_p = card.power
    base_t = card.toughness
    dynamic_p, dynamic_t = _self_defined_card_type_pt(state, card)
    if dynamic_p is not None:
        base_p = dynamic_p
    if dynamic_t is not None:
        base_t = dynamic_t
    # Minimal layer support: base PT setters from static text.
    for src_id in _all_battlefield_ids(state):
        src = state.cards.get(src_id)
        if not src:
            continue
        for scope, other_only, subject, p_set, t_set in _iter_pt_setters(src):
            if src_id == card_id and other_only:
                continue
            if not _scope_controller(src.controller, scope, card.controller):
                continue
            if not _subject_matches(state, card_id, subject):
                continue
            base_p, base_t = p_set, t_set
    return base_p, base_t


def _self_defined_card_type_pt(state, card) -> tuple[int | None, int | None]:
    """Resolve characteristic-defining PT from distinct graveyard card types."""
    text = (getattr(card, "oracle_text", "") or "").lower()
    if not CARD_TYPE_COUNT_RE.search(text):
        return (None, None)
    types: set[str] = set()
    for player in state.players.values():
        for cid in player.graveyard:
            grave_card = state.cards.get(cid)
            if grave_card is not None:
                types.update(str(value).lower() for value in (getattr(grave_card, "types", []) or []))
    count = len(types)
    power = count if "power is equal" in text or "power and toughness" in text else None
    toughness = count + 1 if "toughness is equal to that number plus 1" in text else None
    return power, toughness


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
        if src_id == card_id:
            self_p, self_t = _self_scaling_pt_delta(state, src)
            p_bonus += self_p
            t_bonus += self_t
    return p_bonus, t_bonus


def _self_scaling_pt_delta(state, source_card) -> tuple[int, int]:
    text = (getattr(source_card, "oracle_text", "") or "").lower()
    total_p = 0
    total_t = 0

    for m in SELF_SCALE_GRAVE_RE.finditer(text):
        p_step = int(m.group(1))
        t_step = int(m.group(2))
        selector = (m.group(3) or "").strip()
        scope = (m.group(4) or "your").strip()
        if scope == "all":
            grave_ids: list[str] = []
            for pid in state.players:
                grave_ids.extend(list(state.players[pid].graveyard))
        else:
            grave_ids = list(state.players[source_card.controller].graveyard)
        count = sum(1 for cid in grave_ids if _graveyard_card_matches_selector(state.cards.get(cid), selector))
        total_p += p_step * count
        total_t += t_step * count

    for m in SELF_SCALE_BF_RE.finditer(text):
        p_step = int(m.group(1))
        t_step = int(m.group(2))
        other_only = bool((m.group(3) or "").strip())
        selector = (m.group(4) or "").strip()
        bf_ids = list(state.players[source_card.controller].battlefield)
        count = 0
        for cid in bf_ids:
            if other_only and cid == source_card.id:
                continue
            c = state.cards.get(cid)
            if _battlefield_card_matches_selector(c, selector):
                count += 1
        total_p += p_step * count
        total_t += t_step * count

    return total_p, total_t


def _iter_pt_modifiers(source_card):
    text = (getattr(source_card, "oracle_text", "") or "").lower()
    for match in PT_STATIC_RE.finditer(text):
        other_only = bool(match.group(1))
        subject = match.group(2).strip()
        scope = match.group(3).strip()
        p_delta = int(match.group(4))
        t_delta = int(match.group(5))
        yield (scope, other_only, subject, p_delta, t_delta)


def _iter_pt_setters(source_card):
    text = (getattr(source_card, "oracle_text", "") or "").lower()
    scoped_matches = False
    for match in PT_SET_SCOPE_RE.finditer(text):
        scoped_matches = True
        other_only = bool(match.group(1))
        subject = match.group(2).strip()
        scope = match.group(3).strip()
        p_set, t_set = _extract_pt_set_groups(match)
        if p_set is not None and t_set is not None:
            yield (scope, other_only, subject, p_set, t_set)
    if not scoped_matches:
        for match in PT_SET_RE.finditer(text):
            p_set, t_set = _extract_pt_set_groups(match)
            if p_set is not None and t_set is not None:
                yield ("you control", False, "creatures", p_set, t_set)


def _iter_keyword_grants(source_card):
    text = (getattr(source_card, "oracle_text", "") or "").lower()
    for match in PT_AND_KW_STATIC_RE.finditer(text):
        other_only = bool(match.group(1))
        subject = match.group(2).strip()
        scope = match.group(3).strip()
        granted_text = match.group(4).strip()
        granted = [kw for kw in KNOWN_KEYWORDS if kw in granted_text]
        if granted:
            yield (scope, other_only, subject, granted)
    for match in KW_STATIC_RE.finditer(text):
        other_only = bool(match.group(1))
        subject = match.group(2).strip()
        scope = match.group(3).strip()
        granted_text = match.group(4).strip()
        granted = [kw for kw in KNOWN_KEYWORDS if kw in granted_text]
        if granted:
            yield (scope, other_only, subject, granted)


def _iter_keyword_removals(source_card):
    text = (getattr(source_card, "oracle_text", "") or "").lower()
    for match in PT_AND_KW_REMOVE_RE.finditer(text):
        other_only = bool(match.group(1))
        subject = match.group(2).strip()
        scope = match.group(3).strip()
        removed_text = match.group(4).strip()
        if "all abilities" in removed_text:
            yield (scope, other_only, subject, {"all abilities"})
            continue
        removed = [kw for kw in KNOWN_KEYWORDS if kw in removed_text]
        if removed:
            yield (scope, other_only, subject, set(removed))
    for match in KW_REMOVE_RE.finditer(text):
        other_only = bool(match.group(1))
        subject = match.group(2).strip()
        scope = match.group(3).strip()
        removed_text = match.group(4).strip()
        if "all abilities" in removed_text:
            yield (scope, other_only, subject, {"all abilities"})
            continue
        removed = [kw for kw in KNOWN_KEYWORDS if kw in removed_text]
        if removed:
            yield (scope, other_only, subject, set(removed))
    for match in KW_CANT_HAVE_RE.finditer(text):
        other_only = bool(match.group(1))
        subject = match.group(2).strip()
        scope = match.group(3).strip()
        removed_text = match.group(4).strip()
        removed = [kw for kw in KNOWN_KEYWORDS if kw in removed_text]
        if removed:
            yield (scope, other_only, subject, set(removed))


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


def _graveyard_card_matches_selector(card, selector: str) -> bool:
    if not card:
        return False
    s = selector.strip().lower()
    if s in {"", "card"}:
        return True
    type_map = {
        "creature": "Creature",
        "instant": "Instant",
        "sorcery": "Sorcery",
        "artifact": "Artifact",
        "enchantment": "Enchantment",
        "land": "Land",
        "planeswalker": "Planeswalker",
    }
    if s in type_map:
        return type_map[s] in (getattr(card, "types", []) or [])
    if s.endswith("s") and s[:-1] in type_map:
        return type_map[s[:-1]] in (getattr(card, "types", []) or [])
    if "Creature" not in (getattr(card, "types", []) or []):
        return False
    if s.endswith("s"):
        s = s[:-1]
    return _has_subtype(card, s)


def _battlefield_card_matches_selector(card, selector: str) -> bool:
    if not card:
        return False
    s = selector.strip().lower()
    if s in {"creature", "creatures"}:
        return "Creature" in (getattr(card, "types", []) or [])
    if s in {"artifact creature", "artifact creatures"}:
        return "Creature" in (getattr(card, "types", []) or []) and "Artifact" in (getattr(card, "types", []) or [])
    if s.endswith(" creatures"):
        tribe = s.replace(" creatures", "").strip()
        return _has_subtype(card, tribe)
    if s.endswith("s"):
        s = s[:-1]
    return _has_subtype(card, s)


def _all_battlefield_ids(state) -> list[str]:
    ids: list[str] = []
    battlefield_index = _battlefield_position_map(state)
    for pid in state.players:
        ids.extend(list(state.players[pid].battlefield))
    ids.sort(
        key=lambda cid: (
            effect_timestamp(state.cards.get(cid)),
            int(getattr(state.cards.get(cid), "entered_turn", 0) or 0),
            int(battlefield_index.get(cid, 0) or 0),
            str(cid),
        )
    )
    return ids


def _battlefield_position_map(state) -> dict[str, int]:
    positions: dict[str, int] = {}
    position = 0
    for pid in sorted(state.players):
        for cid in state.players[pid].battlefield:
            positions[cid] = position
            position += 1
    return positions


def _is_battlefield(card) -> bool:
    return getattr(card, "zone", None) == Zone.BATTLEFIELD


def continuous_layer_trace(state, card_id: str) -> dict[str, Any]:
    """Return a deterministic trace of continuous effect application for diagnostics."""
    card = state.cards[card_id]
    trace: list[dict[str, Any]] = []
    applied_layers: list[tuple[tuple[int, int, int, int, int, str], dict[str, Any]]] = []
    layer_index = 0
    for src_id in _all_battlefield_ids(state):
        src = state.cards.get(src_id)
        if not src or not _is_battlefield(src):
            continue
        layer_entries = _source_continuous_layer_entries(state, src, card_id)
        layers = [entry["layer"] for entry in layer_entries]
        if not layers:
            continue
        for entry in layer_entries:
            applied_layers.append(
                (
                    _continuous_layer_sort_key(state, src_id, entry["layer"]),
                    {
                        "source_id": src_id,
                        "source_name": src.name,
                        "layer": entry["layer"],
                    },
                )
            )
        trace.append(
            {
                "source_id": src_id,
                "source_name": src.name,
                "static_order": int(getattr(src, "static_order", 0) or 0),
                "effect_timestamp": effect_timestamp(src),
                "entered_turn": int(getattr(src, "entered_turn", 0) or 0),
                "layers": layers,
            }
        )
    return {
        "card_id": card_id,
        "card_name": card.name,
        "effective_power": effective_power(state, card_id),
        "effective_toughness": effective_toughness(state, card_id),
        "applied_layers": [
            {**entry, "layer_index": index}
            for index, (_, entry) in enumerate(sorted(applied_layers, key=lambda item: item[0]))
        ],
        "trace": trace,
    }


def _source_continuous_layer_entries(state, source_card, target_card_id: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not _is_battlefield(state.cards[target_card_id]):
        return entries
    target = state.cards[target_card_id]
    for scope, other_only, subject, p_delta, t_delta in _iter_pt_modifiers(source_card):
        if _scope_controller(source_card.controller, scope, target.controller) and not (other_only and source_card.id == target_card_id) and _subject_matches(state, target_card_id, subject):
            entries.append({"layer": f"pt-mod:{p_delta}/{t_delta}"})
            break
    for scope, other_only, subject, _p_set, _t_set in _iter_pt_setters(source_card):
        if _scope_controller(source_card.controller, scope, target.controller) and not (other_only and source_card.id == target_card_id) and _subject_matches(state, target_card_id, subject):
            entries.append({"layer": "pt-set"})
            break
    for scope, other_only, subject, granted in _iter_keyword_grants(source_card):
        if _scope_controller(source_card.controller, scope, target.controller) and not (other_only and source_card.id == target_card_id) and _subject_matches(state, target_card_id, subject):
            entries.append({"layer": f"keyword-grant:{','.join(granted)}"})
            break
    for scope, other_only, subject, removed in _iter_keyword_removals(source_card):
        if _scope_controller(source_card.controller, scope, target.controller) and not (other_only and source_card.id == target_card_id) and _subject_matches(state, target_card_id, subject):
            label = "all-abilities" if "all abilities" in removed else ",".join(sorted(removed))
            entries.append({"layer": f"keyword-remove:{label}"})
            break
    return entries


def _source_continuous_layers(state, source_card, target_card_id: str) -> list[str]:
    return [entry["layer"] for entry in _source_continuous_layer_entries(state, source_card, target_card_id)]


def _extract_pt_set_groups(match: re.Match) -> tuple[int | None, int | None]:
    if match.re is PT_SET_SCOPE_RE:
        pairs = ((4, 5), (6, 7), (8, 9))
    else:
        pairs = ((1, 2), (3, 4), (5, 6))
    for p_idx, t_idx in pairs:
        p = match.group(p_idx)
        t = match.group(t_idx)
        if p is not None and t is not None:
            return int(p), int(t)
    return None, None
