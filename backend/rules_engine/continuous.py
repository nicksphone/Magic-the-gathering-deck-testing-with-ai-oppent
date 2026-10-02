from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache, wraps
from typing import Any

from game_state.state import Zone
from rules_engine.card_types import creature_subtype_candidates, CREATURE_SUBTYPES
from rules_engine.card_types import is_token_card
from rules_engine.oracle_text import without_reminder_text
from rules_engine.player_counters import counter_count, PLAYER_COUNT_RE

STATIC_SUBJECT = r"(creature tokens|(?:[a-z]+(?:-[a-z]+)? )*creatures|[a-z]+s?)"
_STATIC_TYPE_NOUNS = {kind.lower() + "s": kind for kind in
                      ("Creature", "Artifact", "Enchantment", "Land", "Planeswalker", "Battle")}
_COLOR_SYMBOLS = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}
ATTACHED_SUBJECT = r"\b(?:equipped|enchanted|fortified) (creature|permanent|land) "
ATTACHED_PT_RE = re.compile(ATTACHED_SUBJECT + r"gets? (?:an additional )?([+-]\d+)/([+-]\d+)(?: for each (.+?))?(?: and has (.+))?")
ATTACHED_KW_RE = re.compile(ATTACHED_SUBJECT + r"has (.+)")
ATTACHED_BASE_RE = re.compile(ATTACHED_SUBJECT + r"has base power and toughness (\d+)/(\d+)(?: and has (.+))?")
GLOBAL_BASE_RE = re.compile(r"\b(?:(all|other) )?creatures (?:have|lose all abilities and have) base power and toughness (\d+)/(\d+)")


def _attached_effects(state, source, target):
    """Only the current attachment receives supported static bonuses."""
    if (not getattr(source, "attached_to", None) or source.attached_to != getattr(target, "id", None) or not _is_battlefield(source)
            or not _is_battlefield(target) or "Creature" in source.types):
        return (0, 0, [], [])
    text = _attached_static_text(source)

    def matches(subject):
        return subject == "permanent" or subject.title() in target.types

    power = toughness = 0
    keywords = set()
    unsupported = []
    previous_condition = None
    previous_subject = None
    for clause in re.split(r"[.\n]", text):
        clause = clause.strip()
        otherwise = clause.startswith("otherwise, ")
        if otherwise:
            if previous_condition is True:
                continue
            if previous_condition is None:
                unsupported.append(clause)
                continue
            clause = clause.removeprefix("otherwise, ")
            clause = re.sub(r"^it\b", previous_subject or "enchanted creature", clause)
        else:
            previous_condition = None
            previous_subject = None
            prefix = re.fullmatch(r"as long as (.+?), (.+)", clause)
            suffix = re.fullmatch(r"(.+?) as long as (.+)", clause)
            if prefix or suffix:
                body, condition = (prefix.group(2), prefix.group(1)) if prefix else suffix.groups()
                subject = re.search(r"\b(?:equipped|enchanted|fortified) (?:creature|permanent|land)\b", body + " " + condition)
                if not subject:
                    continue
                previous_subject = subject.group(0)
                previous_condition = _attached_condition(state, source, target, condition)
                if previous_condition is None:
                    unsupported.append(clause)
                    continue
                if not previous_condition:
                    continue
                clause = re.sub(r"^it\b", previous_subject, body)
        subject = re.search(ATTACHED_SUBJECT, clause)
        if not subject or not matches(subject.group(1)):
            if otherwise:
                unsupported.append(clause)
            continue
        pt = ATTACHED_PT_RE.fullmatch(clause)
        kw = ATTACHED_KW_RE.fullmatch(clause)
        base = ATTACHED_BASE_RE.fullmatch(clause)
        if not pt and not kw and not base:
            from rules_engine.hooks import equip_cost_modifier, aura_cost_modifier
            from rules_engine.attachments import is_aura
            if is_aura(source) and (equip_cost_modifier(clause) or aura_cost_modifier(clause)):
                continue
            unsupported.append(clause)
            continue
        count = _attached_scale_count(state, source, target, pt.group(4)) if pt else 1
        keyword_text = pt.group(5) if pt else base.group(4) if base else kw.group(2)
        granted = _attached_keywords(keyword_text)
        if count is None or granted is None:
            unsupported.append(clause)
        if pt and count is not None:
            power += int(pt.group(2)) * count
            toughness += int(pt.group(3)) * count
        if granted is not None:
            keywords.update(granted)
    return power, toughness, sorted(keywords), unsupported


def _attached_static_text(source):
    lines = []
    for line in without_reminder_text(source.oracle_text or "").lower().splitlines():
        line = re.sub(r"^(?:domain|threshold|metalcraft|delirium)\s*[—–-]\s*", "", line.strip())
        if re.match(r"^(?:when|whenever|at the beginning|if|during)\b", line):
            continue
        line = re.sub(r'"[^"]*"|\u201c[^\u201d]*\u201d', '""', line)
        if ":" not in line and "until end of turn" not in line:
            lines.append(line)
    return "\n".join(lines)


def _attached_condition(state, source, target, condition):
    from rules_engine.colors import card_color_symbols
    words = {word: i for i, word in enumerate(("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"))}

    def number(text):
        return int(text) if text.isdigit() else words.get(text)

    characteristic = re.fullmatch(r"(?:it's|it is|(?:equipped|enchanted|fortified) (?:creature|permanent|land) is) (an? )?([a-z]+)", condition)
    if characteristic:
        article, kind = characteristic.groups()
        if kind in _COLOR_SYMBOLS:
            return _COLOR_SYMBOLS[kind] in card_color_symbols(target)
        if kind.title() in {"Artifact", "Enchantment", "Creature", "Land", "Planeswalker", "Battle"}:
            return kind.title() in target.types
        return _has_subtype(target, kind) if article and kind in CREATURE_SUBTYPES else None
    permanent = re.fullmatch(r"(you|an opponent|your opponents) controls? an? (.+?) permanent", condition)
    if permanent:
        scope, colors = permanent.groups()
        mode = " and " if " and " in colors else " or "
        colors = colors.split(mode)
        if any(color not in _COLOR_SYMBOLS for color in colors):
            return None
        needed = {_COLOR_SYMBOLS[color] for color in colors}
        players = [source.controller] if scope == "you" else [pid for pid in state.players if pid != source.controller]
        return any((needed <= card_color_symbols(state.cards[cid]) if mode == " and " else bool(needed & card_color_symbols(state.cards[cid])))
                   for pid in players for cid in state.players[pid].battlefield)
    graveyard = re.fullmatch(r"there are (\w+) or more cards in your graveyard", condition)
    counters = re.fullmatch(r"this (?:equipment|aura|permanent) has (\w+) or more counters on it", condition)
    if graveyard or counters:
        minimum = number((graveyard or counters).group(1))
        if minimum is None:
            return None
        amount = len(state.players[source.controller].graveyard) if graveyard else sum(
            max(0, value) for name, value in source.counters.items() if not name.startswith("__"))
        return amount >= minimum
    return None


def _attached_keywords(text):
    if text is None:
        return []
    found = []
    remainder = text
    from rules_engine.ward import MANA_WARD
    for match in MANA_WARD.finditer(text):
        found.extend(["ward", f"ward {match[1]}"])
    remainder = MANA_WARD.sub("", remainder)
    from rules_engine.protection import HEXPROOF_VARIANT_RE, hexproof_variants
    for match in HEXPROOF_VARIANT_RE.finditer(remainder):
        found.extend(hexproof_variants(match[0]))
    remainder = HEXPROOF_VARIANT_RE.sub('',remainder)
    for keyword in sorted(KNOWN_KEYWORDS, key=len, reverse=True):
        pattern = r"\b" + re.escape(keyword) + r"\b"
        if re.search(pattern, remainder):
            found.append(keyword)
            remainder = re.sub(pattern, "", remainder)
    return found if not re.sub(r"\band\b|[,\s]", "", remainder) else None


def _attached_scale_count(state, source, target, phrase):
    if phrase is None:
        return 1
    if phrase == "basic land type among lands you control":
        from rules_engine.domain import basic_land_type_count
        return basic_land_type_count(state, source.controller)
    if phrase == "of its colors":
        from rules_engine.colors import card_color_symbols
        return len(card_color_symbols(target))
    if phrase == "aura and equipment attached to it":
        from rules_engine.attachments import is_aura, is_equipment
        return sum((is_aura(card) or is_equipment(card)) and card.attached_to == target.id
                   for card in state.cards.values() if _is_battlefield(card))
    counter = re.fullmatch(r"(?:(.+?) )?counter on this (?:equipment|aura|permanent)", phrase)
    if counter:
        kind = counter.group(1)
        return sum(max(0, amount) for name, amount in source.counters.items()
                   if not name.startswith("__") and (kind is None or name.lower() == kind))
    battlefield = re.fullmatch(r"(other )?(.+?) you control", phrase)
    if not battlefield:
        return None
    other, selectors = battlefield.groups()
    selectors = re.split(r" and/or | or | and ", selectors)
    # Only explicit supported types/subtypes; never turn an unknown predicate into one.
    allowed = {"artifact", "enchantment", "creature", "land", "planeswalker", "battle",
               "plains", "island", "swamp", "mountain", "forest", "gate"}
    if not selectors or any(selector not in allowed for selector in selectors):
        return None

    def selected(card):
        subtype = (card.type_line or "").lower().split("—", 1)[-1].split()
        return any(selector.title() in card.types or ("Land" in card.types and selector in subtype)
                   for selector in selectors)

    return sum(selected(state.cards[cid]) for cid in state.players[source.controller].battlefield
               if not other or cid != target.id)


def attachment_effect_warnings(state, card_id):
    source = state.cards[card_id]
    target = state.cards.get(getattr(source, "attached_to", None))
    return _attached_effects(state, source, target)[3] if target else []


def _static_oracle_text(source_card) -> str:
    """Do not turn later activated/triggered effects into permanent layers."""
    return _static_text_from_oracle(getattr(source_card, "oracle_text", "") or "")


@lru_cache(maxsize=4096)
def _static_text_from_oracle(oracle_text: str) -> str:
    lines = []
    text = without_reminder_text(oracle_text).lower()
    for line in text.splitlines():
        line = line.strip()
        if re.match(r"^(?:when|whenever|at the beginning|if|as long as|during)\b", line):
            continue
        # Quoted granted abilities are not instructions being applied now.
        line = re.sub(r'"[^"]*"|\u201c[^\u201d]*\u201d', '""', line)
        if ":" not in line and "until end of turn" not in line:
            lines.append(line)
    return "\n".join(lines)


PT_STATIC_RE = re.compile(
    r"\b(other\s+)?" + STATIC_SUBJECT + r"\s+"
    r"(you control|your opponents control)\s+get\s+([+-]\d+)\/([+-]\d+)"
)
PT_SET_RE = re.compile(
    r"\b(?:base power and toughness\s+(\d+)\/(\d+)|(?:are|become|becomes|is)\s+(\d+)\/(\d+)|set(?:s)?(?:\s+their)?\s+base power and toughness\s+(\d+)\/(\d+))\b"
)
PT_SET_SCOPE_RE = re.compile(
    r"\b(other\s+)?" + STATIC_SUBJECT + r"\s+"
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
    r"\b(other\s+)?" + STATIC_SUBJECT + r"\s+"
    r"(you control|your opponents control)\s+(?:have|has)\s+([^.]*)"
)
PT_AND_KW_STATIC_RE = re.compile(
    r"\b(other\s+)?" + STATIC_SUBJECT + r"\s+"
    r"(you control|your opponents control)\s+get\s+[+-]\d+\/[+-]\d+\s+and\s+(?:have|has)\s+([^.]*)"
)
PLAYER_COUNTER_PT_RE = re.compile(
    r"(other\s+)?" + STATIC_SUBJECT + r"\s+(you control|your opponents control)\s+"
    r"get\s+([+-]\d+)/([+-]\d+) for each ([a-z-]+) counter you have"
)
SELF_PLAYER_COUNTER_PT_RE = re.compile(r"(.+?) gets ([+-]\d+)/([+-]\d+) for each ([a-z-]+) counter you have")
KW_REMOVE_RE = re.compile(
    r"\b(other\s+)?" + STATIC_SUBJECT + r"\s+"
    r"(you control|your opponents control)\s+(?:lose|loses)\s+([^.]*)"
)
KW_CANT_HAVE_RE = re.compile(
    r"\b(other\s+)?" + STATIC_SUBJECT + r"\s+"
    r"(you control|your opponents control)\s+"
    r"(?:(?:lose|loses)\s+[^.]+?\s+and\s+)?(?:can't|cannot) have(?: or gain)?\s+([^.]*)"
)
PT_AND_KW_REMOVE_RE = re.compile(
    r"\b(other\s+)?" + STATIC_SUBJECT + r"\s+"
    r"(you control|your opponents control)\s+get\s+[+-]\d+\/[+-]\d+\s+and\s+(?:lose|loses)\s+([^.]*)"
)
KNOWN_KEYWORDS = [
    "exalted",
    "decayed",
    "banding",
    "training",
    "trample",
    "first strike",
    "double strike",
    "haste",
    "flash",
    "lifelink",
    "deathtouch",
    "infect",
    "wither",
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


def effective_combat_stats(state, card_id: str) -> tuple[int | None, int | None]:
    """Public stats preserve unknown characteristics rather than inventing zero."""
    base_power, base_toughness = _base_pt_with_layers(state, card_id)
    return (effective_power(state, card_id) if base_power is not None else None,
            effective_toughness(state, card_id) if base_toughness is not None else None)


def _counter_pt_delta(card) -> int:
    """Return PT bonus from +1/+1 and -1/-1 counters on a card."""
    bonus = 0
    for counter, amount in (getattr(card, "counters", {}) or {}).items():
        if counter == "+1/+1":
            bonus += int(amount)
        elif counter == "-1/-1":
            bonus -= int(amount)
    return bonus


def effective_keyword_counts(state, card_id: str) -> dict[str, int]:
    card = state.cards[card_id]
    out = Counter(str(k).lower() for k in (getattr(card, "keywords", None) or []))
    # Scryfall's keyword metadata is unique; standalone Oracle instances aren't.
    printed = Counter(part.strip().lower() for line in without_reminder_text(getattr(card, 'oracle_text', '') or '').splitlines()
                      for part in line.split(',') if part.strip().lower() in {'exalted', 'decayed'})
    for keyword, amount in printed.items():
        out[keyword] = max(out[keyword], amount)
    from rules_engine.protection import hexproof_variants
    printed_parts = [part.strip().lower() for line in without_reminder_text(getattr(card,'oracle_text','') or '').splitlines()
                     for part in line.split(',')]
    variants = [keyword for part in printed_parts for keyword in hexproof_variants(part)]
    if variants:
        out.pop('hexproof from', None)  # Scryfall metadata omits the quality.
        if not any(part.rstrip('.') == 'hexproof' for part in printed_parts):
            out.pop('hexproof', None)  # Metadata includes the family, not a second unrestricted ability.
        for keyword in variants:
            out[keyword] = max(out[keyword], 1)
    from rules_engine.named_counters import keyword_counter
    stamps = getattr(card, 'counter_timestamps', {}) or {}
    counter_grants = sorted((int(stamps.get(kind, effect_timestamp(card))), keyword_counter(kind))
                            for kind, amount in (getattr(card, 'counters', {}) or {}).items()
                            if amount > 0 and keyword_counter(kind))
    if not _is_battlefield(card):
        out.update(keyword for _, keyword in counter_grants)
        return dict(sorted(out.items()))
    modifiers = _resolved_keyword_modifiers(card)
    modifiers.extend({'timestamp': stamp, 'keyword': keyword, 'operation': 'grant', 'count': 1}
                     for stamp, keyword in counter_grants)
    modifiers.sort(key=lambda effect: effect['timestamp'])
    modifier_index = 0
    for src_id in _all_battlefield_ids(state):
        src = state.cards.get(src_id)
        if not src:
            continue
        while modifier_index < len(modifiers) and modifiers[modifier_index]['timestamp'] <= effect_timestamp(src):
            _apply_keyword_modifier(out,modifiers[modifier_index])
            modifier_index += 1
        out.update(_attached_effects(state, src, card)[2])
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
                        for keyword in removed:
                            _remove_keyword_family(out, keyword)
    for modifier in modifiers[modifier_index:]:
        _apply_keyword_modifier(out,modifier)
    # "Can't have" is an override in the keyword layer, not a timestamped
    # ordinary removal. Apply it after all grants and normal removals.
    for src_id in _all_battlefield_ids(state):
        src = state.cards.get(src_id)
        if not src:
            continue
        for scope, other_only, subject, removed in _iter_keyword_cant_removals(src):
            if _scope_controller(src.controller, scope, card.controller):
                if other_only and src_id == card_id:
                    continue
                if _subject_matches(state, card_id, subject):
                    if "all abilities" in removed:
                        out.clear()
                    else:
                        for keyword in removed:
                            _remove_keyword_family(out, keyword)
    return dict(sorted(out.items()))


def effective_keywords(state, card_id: str) -> list[str]:
    return list(effective_keyword_counts(state, card_id))


def _remove_keyword_family(keywords, keyword):
    for present in list(keywords):
        if present == keyword or keyword == 'hexproof' and present.startswith('hexproof from '):
            keywords.pop(present, None)


def _resolved_keyword_modifiers(card):
    from rules_engine.keyword_effects import active_keyword_effects
    effects = [{**effect, 'count': 1} for effect in active_keyword_effects(card)]
    effects.extend({'keyword': key.removeprefix('__eot_keyword_'), 'operation': 'grant',
                    'timestamp': effect_timestamp(card), 'count': amount,
                    'until_end_of_turn': True, 'timestamp_origin': 'legacy_inferred'}
                   for key,amount in (getattr(card,'counters',{}) or {}).items()
                   if key.startswith('__eot_keyword_') and amount > 0)
    return effects


def _apply_keyword_modifier(keywords, effect):
    if effect['operation'] == 'remove':
        _remove_keyword_family(keywords,effect['keyword'])
    else:
        keywords[effect['keyword']] += effect['count']


def printed_abilities_suppressed(state, card_id: str) -> bool:
    """Supported all-ability losses; new keyword grants do not restore Oracle abilities."""
    card = state.cards.get(card_id)
    if card is None or not _is_battlefield(card):
        return False
    for source_id in _all_battlefield_ids(state):
        source = state.cards[source_id]
        for scope, other_only, subject, removed in _iter_keyword_removals(source):
            if ('all abilities' in removed
                    and (not other_only or source_id != card_id)
                    and _scope_controller(source.controller, scope, card.controller)
                    and _subject_matches(state, card_id, subject)):
                return True
    return False


def has_keyword(state, card_id: str, keyword: str) -> bool:
    k = (keyword or "").lower()
    keywords = effective_keywords(state, card_id)
    return k in keywords or k == 'hexproof' and any(value.startswith('hexproof from ') for value in keywords)


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
            if not _pt_setter_applies(state, src, card_id, scope, other_only, subject):
                continue
            base_p, base_t = p_set, t_set
    return base_p, base_t


def _self_defined_card_type_pt(state, card) -> tuple[int | None, int | None]:
    """Resolve supported characteristic-defining power/toughness clauses."""
    text = (getattr(card, "oracle_text", "") or "").lower()
    for line in _static_oracle_text(card).splitlines():
        match = re.fullmatch(r"this creature's power and toughness are each equal to the " + PLAYER_COUNT_RE + r"\.?", line.strip())
        if match:
            count = counter_count(state.players[card.controller], match[1])
            return count, count
    if "power is equal to the number of creatures you control" in text:
        return (sum("Creature" in state.cards[cid].types for cid in state.players[card.controller].battlefield), None)
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
        attached_p, attached_t, _, _ = _attached_effects(state, src, card)
        p_bonus += attached_p
        t_bonus += attached_t
        counter_p, counter_t = _player_counter_pt_bonus(state, src, card)
        p_bonus += counter_p
        t_bonus += counter_t
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


def _static_parser(parser):
    """Cache immutable instructions by text, never effective mutable game state."""
    cached = lru_cache(maxsize=4096)(lambda text: tuple(parser(text)))

    @wraps(parser)
    def instructions(source_card):
        return iter(cached(_static_oracle_text(source_card)))

    instructions.uncached = lambda source_card: parser(_static_oracle_text(source_card))
    instructions.cache_info = cached.cache_info
    instructions.cache_clear = cached.cache_clear
    return instructions


@_static_parser
def _iter_player_counter_modifiers(text):
    if 'counter you have' not in text:
        return
    for line in text.splitlines():
        line = line.strip().rstrip('.')
        match = PLAYER_COUNTER_PT_RE.fullmatch(line)
        if match:
            yield (match[3], bool(match[1]), match[2], int(match[4]), int(match[5]), match[6])
        elif (match := SELF_PLAYER_COUNTER_PT_RE.fullmatch(line)):
            yield ('self', False, match[1], int(match[2]), int(match[3]), match[4])


def _player_counter_pt_bonus(state, source, target):
    power = toughness = 0
    for scope, other, subject, p, t, counter in _iter_player_counter_modifiers(source):
        if scope == 'self':
            if source.id != target.id or subject not in {source.name.lower(), source.name.split(',')[0].lower(), 'this creature', 'this permanent'}:
                continue
        elif ((other and source.id == target.id) or not _scope_controller(source.controller, scope, target.controller)
              or not _subject_matches(state, target.id, subject)):
            continue
        count = counter_count(state.players[source.controller], counter)
        power += p * count
        toughness += t * count
    return power, toughness


@_static_parser
def _iter_pt_modifiers(text):
    for match in PT_STATIC_RE.finditer(text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        clause = text[line_start:line_end if line_end != -1 else len(text)]
        if re.search(r'\bfor each [a-z-]+ counter you have\b', clause):
            continue
        if clause.strip().startswith(("when ", "whenever ", "at the beginning")) or "until end of turn" in clause:
            continue
        other_only = bool(match.group(1))
        subject = match.group(2).strip()
        scope = match.group(3).strip()
        p_delta = int(match.group(4))
        t_delta = int(match.group(5))
        yield (scope, other_only, subject, p_delta, t_delta)


@_static_parser
def _iter_pt_setters(text):
    for match in PT_SET_SCOPE_RE.finditer(text):
        other_only = bool(match.group(1))
        subject = match.group(2).strip()
        scope = match.group(3).strip()
        p_set, t_set = _extract_pt_set_groups(match)
        if p_set is not None and t_set is not None:
            yield (scope, other_only, subject, p_set, t_set)
    for clause in re.split(r"[.\n]", text):
        match = ATTACHED_BASE_RE.fullmatch(clause.strip())
        if match:
            yield ("attached", False, match.group(1), int(match.group(2)), int(match.group(3)))
        match = GLOBAL_BASE_RE.fullmatch(clause.strip())
        if match:
            yield ("all", match.group(1) == "other", "creatures", int(match.group(2)), int(match.group(3)))


def _pt_setter_applies(state, source, target_id, scope, other_only, subject):
    target = state.cards[target_id]
    if scope == "attached":
        return (source.attached_to == target_id and "Creature" not in source.types
                and (subject == "permanent" or subject.title() in target.types))
    return ((scope == "all" or _scope_controller(source.controller, scope, target.controller))
            and not (other_only and source.id == target_id)
            and _subject_matches(state, target_id, subject))


@_static_parser
def _iter_keyword_grants(text):
    for match in PT_AND_KW_STATIC_RE.finditer(text):
        other_only = bool(match.group(1))
        subject = match.group(2).strip()
        scope = match.group(3).strip()
        granted_text = match.group(4).strip()
        granted = _static_keyword_grants(granted_text)
        if granted:
            yield (scope, other_only, subject, granted)
    for match in KW_STATIC_RE.finditer(text):
        other_only = bool(match.group(1))
        subject = match.group(2).strip()
        scope = match.group(3).strip()
        granted_text = match.group(4).strip()
        granted = _static_keyword_grants(granted_text)
        if granted:
            yield (scope, other_only, subject, granted)


def _static_keyword_grants(text):
    from rules_engine.protection import HEXPROOF_VARIANT_RE, hexproof_variants
    variants = tuple(keyword for match in HEXPROOF_VARIANT_RE.finditer(text) for keyword in hexproof_variants(match[0]))
    remainder = HEXPROOF_VARIANT_RE.sub('',text)
    return variants + tuple(kw for kw in KNOWN_KEYWORDS if kw in remainder
                            and (kw != 'hexproof' or re.search(r'\bhexproof\b(?!\s+from\b)',remainder)))


@_static_parser
def _iter_keyword_removals(text):
    for clause in re.split(r'[.\n]', text):
        match = re.fullmatch(r'(?:all )?creatures lose all abilities(?: and have base power and toughness \d+/\d+)?', clause.strip())
        if match:
            yield ('all', False, 'creatures', frozenset({'all abilities'}))
    for match in PT_AND_KW_REMOVE_RE.finditer(text):
        other_only = bool(match.group(1))
        subject = match.group(2).strip()
        scope = match.group(3).strip()
        removed_text = match.group(4).strip()
        if "all abilities" in removed_text:
            yield (scope, other_only, subject, frozenset({"all abilities"}))
            continue
        removed = [kw for kw in KNOWN_KEYWORDS if kw in removed_text]
        if removed:
            yield (scope, other_only, subject, frozenset(removed))
    for match in KW_REMOVE_RE.finditer(text):
        other_only = bool(match.group(1))
        subject = match.group(2).strip()
        scope = match.group(3).strip()
        removed_text = match.group(4).strip()
        if "all abilities" in removed_text:
            yield (scope, other_only, subject, frozenset({"all abilities"}))
            continue
        removed = [kw for kw in KNOWN_KEYWORDS if kw in removed_text]
        if removed:
            yield (scope, other_only, subject, frozenset(removed))


@_static_parser
def _iter_keyword_cant_removals(text):
    for match in KW_CANT_HAVE_RE.finditer(text):
        other_only = bool(match.group(1))
        subject = match.group(2).strip()
        scope = match.group(3).strip()
        removed_text = match.group(4).strip()
        removed = [kw for kw in KNOWN_KEYWORDS if kw in removed_text]
        if removed:
            yield (scope, other_only, subject, frozenset(removed))


def _scope_controller(source_controller: int, scope: str, target_controller: int) -> bool:
    if scope == 'all':
        return True
    if scope == "you control":
        return source_controller == target_controller
    if scope == "your opponents control":
        return source_controller != target_controller
    return False


def _subject_matches(state, card_id: str, subject: str) -> bool:
    card = state.cards[card_id]
    s = (subject or "").strip().lower()
    type_nouns = _STATIC_TYPE_NOUNS
    if s in type_nouns:
        return type_nouns[s] in card.types
    if s == "permanents":
        return _is_battlefield(card) and bool(set(card.types) & set(type_nouns.values()))
    if s == "tokens":
        return is_token_card(card)
    if s == "creature tokens":
        return "Creature" in card.types and is_token_card(card)
    if s.endswith(" creatures"):
        if "Creature" not in card.types:
            return False
        colors = set(getattr(card, "colors", None) or [])
        color_names = _COLOR_SYMBOLS
        front_types = set((getattr(card, "type_line", "") or "").split("—", 1)[0].split("-", 1)[0].lower().split())

        def matches(qualifier):
            negative = qualifier.startswith("non")
            word = qualifier[3:].lstrip("-") if negative else qualifier
            if word == "token":
                matched = is_token_card(card)
            elif word in color_names:
                matched = color_names[word] in colors
            elif word == "colorless":
                matched = not colors
            elif word.title() in type_nouns.values():
                matched = word.title() in card.types
            elif word in {"legendary", "snow"}:
                matched = word in front_types
            else:
                matched = _has_subtype(card, word)
            return not matched if negative else matched

        return all(matches(word) for word in s.removesuffix(" creatures").split())
    return any(_has_subtype(card, singular) for singular in creature_subtype_candidates(s))


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
    if _is_battlefield(card):
        for effect in _resolved_keyword_modifiers(card):
            layer = f"keyword-{'remove' if effect['operation'] == 'remove' else 'grant'}:{effect['keyword']}"
            key = _continuous_layer_sort_key(state,card_id,layer)
            applied_layers.append(((key[0],key[1],effect['timestamp'],*key[3:]), {
                'source_id': effect.get('source_card_id'), 'source_name': effect.get('source_name'),
                'target_id': card_id, 'layer': layer,
                'effect_timestamp': effect['timestamp'], 'timestamp_origin': effect['timestamp_origin'],
                'until_end_of_turn': effect['until_end_of_turn'], 'instance_count': effect['count'],
            }))
    from rules_engine.named_counters import keyword_counter
    for kind, amount in (getattr(card, 'counters', {}) or {}).items():
        keyword = keyword_counter(kind)
        if amount <= 0 or keyword is None:
            continue
        stamp = int((getattr(card, 'counter_timestamps', {}) or {}).get(kind, effect_timestamp(card)))
        key = _continuous_layer_sort_key(state, card_id, f'keyword-grant:{keyword}')
        applied_layers.append(((key[0], key[1], stamp, *key[3:]), {
            'source_id': card_id, 'source_name': card.name,
            'layer': f'keyword-grant:{keyword}', 'counter': kind, 'effect_timestamp': stamp,
        }))
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
        "unsupported_attachment_clauses": [
            {"source_id": cid, "source_name": state.cards[cid].name, "clause": clause}
            for cid in _all_battlefield_ids(state)
            for clause in _attached_effects(state, state.cards[cid], card)[3]
        ],
    }


def _source_continuous_layer_entries(state, source_card, target_card_id: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not _is_battlefield(state.cards[target_card_id]):
        return entries
    target = state.cards[target_card_id]
    counter_p, counter_t = _player_counter_pt_bonus(state, source_card, target)
    if counter_p or counter_t:
        entries.append({"layer": f"pt-mod:{counter_p}/{counter_t}"})
    attached_p, attached_t, attached_keywords, _ = _attached_effects(state, source_card, target)
    if attached_p or attached_t:
        entries.append({"layer": f"pt-mod:{attached_p}/{attached_t}"})
    if attached_keywords:
        entries.append({"layer": f"keyword-grant:{','.join(attached_keywords)}"})
    for scope, other_only, subject, p_delta, t_delta in _iter_pt_modifiers(source_card):
        if _scope_controller(source_card.controller, scope, target.controller) and not (other_only and source_card.id == target_card_id) and _subject_matches(state, target_card_id, subject):
            entries.append({"layer": f"pt-mod:{p_delta}/{t_delta}"})
            break
    for scope, other_only, subject, _p_set, _t_set in _iter_pt_setters(source_card):
        if _pt_setter_applies(state, source_card, target_card_id, scope, other_only, subject):
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
    for scope, other_only, subject, removed in _iter_keyword_cant_removals(source_card):
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
