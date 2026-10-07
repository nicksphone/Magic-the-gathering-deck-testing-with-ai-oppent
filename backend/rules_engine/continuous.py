from __future__ import annotations
from rules_engine.type_effects import effective_types

import re
from collections import Counter
from functools import lru_cache, wraps
from rules_engine.query_context import scoped_query, query_cache
from typing import Any

from game_state.state import Zone
from rules_engine.card_types import creature_subtype_candidates, CREATURE_SUBTYPES
from rules_engine.card_types import is_token_card, CARD_TYPES, graveyard_card_types
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
            or not _is_battlefield(target) or "Creature" in effective_types(state, source)):
        return (0, 0, [], [])
    text = _attached_static_text(source)

    def matches(subject):
        return subject == "permanent" or subject.title() in effective_types(state, target)

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
            from rules_engine.combat_constraints import supported_body
            if supported_body(clause[subject.end():].strip()):
                continue
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
    from rules_engine.static_conditions import static_clause_components
    lines = []
    for line in without_reminder_text(source.oracle_text or "").lower().splitlines():
        line = re.sub(r"^(?:domain|threshold|metalcraft|delirium)\s*[—–-]\s*", "", line.strip())
        if re.match(r"^(?:when|whenever|at the beginning|if|during)\b", line):
            continue
        line = re.sub(r'"[^"]*"|\u201c[^\u201d]*\u201d', '""', line)
        if ":" not in line and "until end of turn" not in line:
            lines.extend(static_clause_components(line))
    return "\n".join(lines)


def _attached_condition(state, source, target, condition):
    from rules_engine.static_conditions import evaluate_static_condition
    return evaluate_static_condition(state, source, target, condition)


def _attached_keywords(text):
    if text is None:
        return []
    found = []
    remainder = text
    from rules_engine.ward import MANA_WARD, parse_ward_cost
    ward = re.search(r'\bward(?:\s*[—-]\s*|\s+)(.+)$', remainder)
    if ward and parse_ward_cost(ward[1]) is not None:
        found.extend(['ward', f'ward {ward[1]}'])
        remainder = remainder[:ward.start()]
    for match in MANA_WARD.finditer(remainder):
        found.extend(["ward", f"ward {match[1]}"])
    remainder = MANA_WARD.sub("", remainder)
    from rules_engine.protection import PROTECTION_CLAUSE_RE, extract_protection_keywords
    for match in PROTECTION_CLAUSE_RE.finditer(remainder):
        found.extend(extract_protection_keywords(match[0]))
    remainder = PROTECTION_CLAUSE_RE.sub('', remainder)
    from rules_engine.protection import HEXPROOF_VARIANT_RE, hexproof_variants
    for match in HEXPROOF_VARIANT_RE.finditer(remainder):
        found.extend(hexproof_variants(match[0]))
    remainder = HEXPROOF_VARIANT_RE.sub('',remainder)
    for match in re.finditer(r'\b(?:bushido|rampage) \d+\b', remainder):
        found.append(match[0])
    remainder = re.sub(r'\b(?:bushido|rampage) \d+\b', '', remainder)
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
        return len(card_color_symbols(target, state))
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
        from rules_engine.land_types import has_land_type
        return any(selector.title() in effective_types(state, card) or ("Land" in effective_types(state, card) and has_land_type(state, card, selector))
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
        if re.match(r"^(?:when|whenever|at the beginning|if|as long as|otherwise|during)\b", line) or 'as long as' in line:
            continue
        # Quoted granted abilities are not instructions being applied now.
        line = re.sub(r'"[^"]*"|\u201c[^\u201d]*\u201d', '""', line)
        if ":" not in line and "until end of turn" not in line:
            lines.append(line)
    return "\n".join(lines)


@lru_cache(maxsize=4096)
def _conditional_static_instructions(oracle_text, name):
    """Compile complete clauses; cache instructions, never predicate results."""
    subject = _self_stat_subject(name)
    from rules_engine.static_conditions import static_clause_components
    result = []
    clauses = [component for line in re.split(r'[.\n]', without_reminder_text(oracle_text).lower())
               for component in static_clause_components(line)]
    for raw in clauses:
        from rules_engine.type_effects import devotion_type_condition
        if devotion_type_condition(raw.strip() + '.', name) is not None:
            continue  # The earlier type layer owns this instruction.
        raw = re.sub(r'"[^"]*"|\u201c[^\u201d]*\u201d', '""', raw.strip())
        line = re.sub(r'^[a-z][a-z ]*\s+[—–-]\s+', '', raw)
        if 'as long as' not in line or ':' in line or 'until end of turn' in line or re.match(r'^(?:when|whenever|at the beginning|if|during)\b', line):
            continue
        prefix = re.fullmatch(r'as long as (.+?), (.+)', line)
        suffix = re.fullmatch(r'(.+?) as long as (.+)', line)
        if not prefix and not suffix:
            continue
        body, condition = (prefix[2], prefix[1]) if prefix else suffix.groups()
        if re.search(ATTACHED_SUBJECT, body):
            continue  # Attachments already use the same predicate evaluator.
        own = re.fullmatch(subject + r' (?:gets ([+-]\d+)/([+-]\d+)(?: and has (.+))?|has (.+))', body)
        pt = re.fullmatch(PT_STATIC_RE.pattern + r'(?: and (?:have|has) (.+))?', body)
        kw = KW_STATIC_RE.fullmatch(body)
        if own:
            keywords = _attached_keywords(own[3] or own[4])
            entry = ('self', False, '', int(own[1] or 0), int(own[2] or 0), keywords)
        elif pt:
            keywords = _attached_keywords(pt[6])
            entry = (pt[3], bool(pt[1]), pt[2], int(pt[4]), int(pt[5]), keywords)
        elif kw:
            keywords = _attached_keywords(kw[4])
            entry = (kw[3], bool(kw[1]), kw[2], 0, 0, keywords)
        else:
            from rules_engine.combat_constraints import supported_body
            combat = re.fullmatch(subject + r' (.+)', body)
            if combat and supported_body(combat[1]):
                continue  # The condition-aware combat layer owns this instruction.
            entry = (None, False, '', 0, 0, None)
        scope, other, recipient, p, t, keywords = entry
        result.append((condition, scope, other, recipient, p, t,
                       tuple(keywords) if keywords is not None else None, raw))
    return tuple(result)


def _conditional_static_effects(state, source, target):
    from rules_engine.static_conditions import evaluate_static_condition
    p = t = 0
    keywords = []
    unsupported = []
    if not _is_battlefield(source) or not _is_battlefield(target):
        return p, t, keywords, unsupported
    for condition, scope, other, subject, dp, dt, granted, raw in _conditional_static_instructions(getattr(source, 'oracle_text', '') or '', getattr(source, 'name', '')):
        active = evaluate_static_condition(state, source, target, condition)
        if scope is None or granted is None or active is None:
            unsupported.append(raw)
            continue
        applies = (source.id == target.id if scope == 'self' else
                   _scope_controller(source.controller, scope, target.controller)
                   and not (other and source.id == target.id) and _subject_matches(state, target.id, subject))
        if active and applies:
            p += dp
            t += dt
            keywords.extend(granted)
    return p, t, keywords, unsupported


def conditional_static_clause_coverage(oracle_text, name=''):
    """Use runtime instruction recognition, never a simulated predicate value."""
    from rules_engine.static_conditions import parse_static_condition
    rows = []
    for condition, scope, _, _, _, _, granted, raw in _conditional_static_instructions(oracle_text, name):
        reasons = []
        if parse_static_condition(condition, name) is None:
            reasons.append('unsupported conditional static predicate')
        if scope is None or granted is None:
            reasons.append('unsupported conditional static instruction')
        if reasons:
            rows.append({'clause': raw, 'condition': condition, 'reasons': reasons})
    return rows


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
    "undying",
    "flanking",
    "bushido",
    "rampage",
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
    if layer.startswith(('type-add:', 'type-remove:')):
        layer_rank = 4
        sublayer = 0
    elif layer.startswith("keyword-"):
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
    return int(effective_combat_stats(state, card_id, unknown_as_zero=True)[0])


def effective_toughness(state, card_id: str) -> int:
    return int(effective_combat_stats(state, card_id, unknown_as_zero=True)[1])


@scoped_query
def effective_combat_stats(state, card_id: str, *, unknown_as_zero=False) -> tuple[int | None, int | None]:
    """Public stats preserve unknown characteristics rather than inventing zero."""
    base_power, base_toughness = _base_pt_with_layers(state, card_id)
    if unknown_as_zero:
        base_power, base_toughness = int(base_power or 0), int(base_toughness or 0)
    power_bonus, toughness_bonus = _continuous_pt_delta(state, card_id)
    counter_bonus = _counter_pt_delta(state.cards[card_id])
    counters = getattr(state.cards[card_id], 'counters', {}) or {}
    return (base_power + power_bonus + counter_bonus + int(counters.get('__eot_power', 0)) if base_power is not None else None,
            base_toughness + toughness_bonus + counter_bonus + int(counters.get('__eot_toughness', 0)) if base_toughness is not None else None)


def _counter_pt_delta(card) -> int:
    """Return PT bonus from +1/+1 and -1/-1 counters on a card."""
    bonus = 0
    for counter, amount in (getattr(card, "counters", {}) or {}).items():
        if counter == "+1/+1":
            bonus += int(amount)
        elif counter == "-1/-1":
            bonus -= int(amount)
    return bonus


@scoped_query
def effective_keyword_counts(state, card_id: str) -> dict[str, int]:
    card = state.cards[card_id]
    out = Counter(str(k).lower() for k in (getattr(card, "keywords", None) or []))
    conditional = {keyword for _, scope, _, _, _, _, keywords, _ in
                   _conditional_static_instructions(getattr(card, 'oracle_text', '') or '', getattr(card, 'name', ''))
                   if scope == 'self' for keyword in keywords or ()}
    if conditional & out.keys():
        from game_state.state import _infer_keywords
        for keyword in conditional - set(_infer_keywords(card.oracle_text or '')):
            out.pop(keyword, None)
    from rules_engine.ward import printed_ward_costs
    ward_costs = printed_ward_costs(card, include_conditionals=False)
    if ward_costs:
        out.update('ward ' + cost.lower() for cost in ward_costs)
        out['ward'] = max(out.get('ward', 0), len(ward_costs))
    # Scryfall's keyword metadata is unique; standalone Oracle instances aren't.
    printed = Counter(part.strip().lower() for line in without_reminder_text(getattr(card, 'oracle_text', '') or '').splitlines()
                      for part in line.split(',') if part.strip().lower() in {'exalted', 'decayed', 'flanking', 'undying'}
                      or re.fullmatch(r'(?:bushido|rampage) \d+', part.strip().lower()))
    for keyword, amount in printed.items():
        out[keyword] = max(out[keyword], amount)
    for family in ('bushido', 'rampage'):
        if any(keyword.startswith(family + ' ') for keyword in out):
            out.pop(family, None)  # Scryfall's family label is not an extra instance.
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
    if card.suspend_haste and card.suspend_haste['controller'] == card.controller and card.zone in {Zone.STACK, Zone.BATTLEFIELD}:
        counter_grants.append((card.suspend_haste['timestamp'], 'haste'))
    if not _is_battlefield(card):
        out.update(keyword for _, keyword in counter_grants)
        return dict(sorted(out.items()))
    from rules_engine.land_types import printed_land_abilities_lost
    if printed_land_abilities_lost(state, card):
        out.clear()
    modifiers = _resolved_keyword_modifiers(card)
    modifiers.extend({'timestamp': stamp, 'keyword': keyword, 'operation': 'grant', 'count': 1}
                     for stamp, keyword in counter_grants)
    modifiers.sort(key=lambda effect: effect['timestamp'])
    modifier_index = 0
    for src_id, src, source_active in _continuous_sources(state):
        while modifier_index < len(modifiers) and modifiers[modifier_index]['timestamp'] <= effect_timestamp(src):
            _apply_keyword_modifier(out,modifiers[modifier_index])
            modifier_index += 1
        if source_active:
            out.update(_attached_effects(state, src, card)[2])
            out.update(_conditional_static_effects(state, src, card)[2])
        for scope, other_only, subject, granted in (_iter_keyword_grants(src) if source_active else ()):
            if _scope_controller(src.controller, scope, card.controller):
                if other_only and src_id == card_id:
                    continue
                if _subject_matches(state, card_id, subject):
                    out.update(granted)
        for scope, other_only, subject, removed in _iter_keyword_removals(src):
            from rules_engine.basic_land_layer import prior_layer_abilities_lost
            if prior_layer_abilities_lost(state, src):
                continue
            if not source_active and 'all abilities' not in removed:
                continue
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
    for src_id, src, source_active in _continuous_sources(state):
        if not source_active:
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
        if (present == keyword or keyword == 'hexproof' and present.startswith('hexproof from ')
                or keyword in {'bushido', 'rampage', 'ward'} and present.startswith(keyword + ' ')):
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
        if effect['keyword'] == 'all abilities':
            keywords.clear()
        else:
            _remove_keyword_family(keywords,effect['keyword'])
    else:
        keywords[effect['keyword']] += effect['count']


@scoped_query
def _printed_ability_loss_sources(state):
    from rules_engine.basic_land_layer import prior_layer_abilities_lost
    losses = []
    # This union of recognized losses does not depend on source timestamp order.
    for player in state.players.values():
        for source_id in player.battlefield:
            source = state.cards.get(source_id)
            if (source is None or 'all abilities' not in _static_oracle_text(source)
                    or prior_layer_abilities_lost(state, source)):
                continue
            for scope, other_only, subject, removed in _iter_keyword_removals(source):
                if 'all abilities' in removed:
                    losses.append((source, scope, other_only, subject))
    return losses


def printed_abilities_suppressed(state, card_id: str, *, losses=None, include_land_types=True) -> bool:
    """Supported all-ability losses; new keyword grants do not restore Oracle abilities."""
    card = state.cards.get(card_id)
    if card is None or not _is_battlefield(card):
        return False
    cache = query_cache(state)
    if cache is None:
        return _printed_suppression_result(state, card_id, card, losses, include_land_types)
    if losses is not None and type(losses) not in (list, tuple):
        return _printed_suppression_result(state, card_id, card, losses, include_land_types)
    loss_key = None if losses is None else tuple(
        (source.id if other_only else None, source.controller, scope, other_only, subject)
        for source, scope, other_only, subject in losses)
    key = (_printed_suppression_result, card_id, loss_key, include_land_types)
    if key not in cache:
        cache[key] = _printed_suppression_result(state, card_id, card, losses, include_land_types)
    return cache[key]


def _printed_suppression_result(state, card_id, card, losses, include_land_types):
    if include_land_types:
        from rules_engine.land_types import printed_land_abilities_lost
        if printed_land_abilities_lost(state, card):
            return True
    from rules_engine.keyword_effects import active_keyword_effects
    if any(effect['operation'] == 'remove' and effect['keyword'] == 'all abilities'
           for effect in active_keyword_effects(card)):
        return True
    if losses is None:
        losses = _printed_ability_loss_sources(state)
    return any((not other_only or source.id != card_id)
               and _scope_controller(source.controller, scope, card.controller)
               and _subject_matches(state, card_id, subject)
               for source, scope, other_only, subject in losses)


def has_keyword(state, card_id: str, keyword: str) -> bool:
    k = (keyword or "").lower()
    keywords = effective_keywords(state, card_id)
    return k in keywords or k == 'hexproof' and any(value.startswith('hexproof from ') for value in keywords)


def _base_pt_with_layers(state, card_id: str) -> tuple[int | None, int | None]:
    card = state.cards[card_id]
    ability_losses = _printed_ability_loss_sources(state)
    base_p = card.power
    base_t = card.toughness
    dynamic_p, dynamic_t = _self_defined_card_type_pt(state, card)
    if printed_abilities_suppressed(state, card_id, losses=ability_losses):
        dynamic_p = _undefined_printed_stat(getattr(card, 'printed_power', None)) if base_p is None and dynamic_p is not None else None
        dynamic_t = _undefined_printed_stat(getattr(card, 'printed_toughness', None)) if base_t is None and dynamic_t is not None else None
    if dynamic_p is not None:
        base_p = dynamic_p
    if dynamic_t is not None:
        base_t = dynamic_t
    # Minimal layer support: base PT setters from static text.
    setters = []
    for src_id, src, source_active in _continuous_sources(state):
        setter_source = src if source_active else _ability_layer_continuation_source(state, src)
        if setter_source is None:
            continue
        for scope, other_only, subject, p_set, t_set in _iter_pt_setters(setter_source):
            if not _pt_setter_applies(state, src, card_id, scope, other_only, subject):
                continue
            setters.append((effect_timestamp(src), p_set, t_set))
    setters.extend((effect['timestamp'], effect['power'], effect['toughness'])
                   for effect in _resolved_base_stat_effects(card))
    if setters:
        _, base_p, base_t = sorted(setters, key=lambda item: item[0])[-1]
    return base_p, base_t


def _resolved_base_stat_effects(card):
    from game_state.state import object_incarnation
    return [effect for effect in getattr(card, 'base_stat_effects', []) if _is_battlefield(card)
            and effect['incarnation'] == object_incarnation(card)]


def _ability_layer_continuation_source(state, source):
    """The supported combined loss/base-PT instruction starts in layer six."""
    from copy import copy
    from rules_engine.basic_land_layer import prior_layer_abilities_lost
    if prior_layer_abilities_lost(state, source):
        return None
    clauses = [clause.strip() for clause in re.split(r'[.\n]', _static_oracle_text(source))
               if re.fullmatch(r'(?:all )?creatures lose all abilities and have base power and toughness \d+/\d+', clause.strip())]
    if not clauses:
        return None
    continued = copy(source)
    continued.oracle_text = '.\n'.join(clauses)
    return continued


def _self_defined_card_type_pt(state, card) -> tuple[int | None, int | None]:
    """Resolve supported characteristic-defining power/toughness clauses."""
    power = toughness = None
    subject = _self_stat_subject(card) + r"'s "
    for line in _static_oracle_text(card).splitlines():
        line = line.strip().rstrip('.').replace('\u2019', "'")
        both = re.fullmatch(subject + r'power and toughness are each equal to (.+)', line)
        pair = re.fullmatch(subject + r'power is equal to (.+) and its toughness is equal to that number plus (\d+)', line)
        single = re.fullmatch(subject + r'(power|toughness) is equal to (.+)', line)
        if both:
            power = toughness = _stat_resource_count(state, card, both[1])
        elif pair:
            power = _stat_resource_count(state, card, pair[1])
            toughness = power + int(pair[2]) if power is not None else None
        elif single:
            count = _stat_resource_count(state, card, single[2])
            if single[1] == 'power':
                power = count
            else:
                toughness = count
    return power, toughness


def _self_stat_subject(card):
    name = str(card if isinstance(card, str) else getattr(card, 'name', '') or '').lower().replace('\u2019', "'")
    names = {name, name.split(',')[0], 'this creature', 'this permanent', 'this card'} - {''}
    return '(?:' + '|'.join(re.escape(value) for value in sorted(names)) + ')'


def _undefined_printed_stat(expression):
    """Use zero for an undefined star inside a recognized printed calculation."""
    if expression is None or expression == '*':
        return 0
    match = re.fullmatch(r'(\d+)\+\*|\*\+(\d+)', expression)
    return int(match[1] or match[2]) if match else 0


def _stat_resource_count(state, card, expression):
    expression = expression.strip().removeprefix('the ')
    pid = card.controller if getattr(card, 'zone', Zone.BATTLEFIELD) in {Zone.BATTLEFIELD, Zone.STACK} else getattr(card, 'owner', card.controller)
    if (match := re.fullmatch(r'(\d+) plus (.+)', expression)):
        count = _stat_resource_count(state, card, match[2])
        return count + int(match[1]) if count is not None else None
    if (match := re.fullmatch(PLAYER_COUNT_RE, expression)):
        return counter_count(state.players[pid], match[1])
    expression = expression.removeprefix('total ').removeprefix('number of ')
    if expression == 'cards in your hand':
        return len(state.players[pid].hand)
    if expression == "cards in all players' hands":
        return sum(len(player.hand) for player in state.players.values())
    match = re.fullmatch(r'(card types among cards|(?:(.+?) )?cards) in (your|all|your opponents\') graveyards?', expression)
    if match:
        players = [pid] if match[3] == 'your' else [3-pid] if match[3] == "your opponents'" else list(state.players)
        cards = [state.cards[cid] for owner in players for cid in state.players[owner].graveyard
                 if cid in state.cards and not is_token_card(state.cards[cid])]
        if match[1] == 'card types among cards':
            return len(graveyard_card_types(state, players))
        return sum(_graveyard_card_matches_selector(value, match[2] or '') for value in cards)
    if (match := re.fullmatch(r'(.+?) you control', expression)):
        selector = match[1].removeprefix('other ')
        return sum(_battlefield_card_matches_selector(state.cards.get(cid), selector, state=state)
                   for cid in state.players[pid].battlefield
                   if not match[1].startswith('other ') or cid != card.id)
    return None


def _continuous_pt_delta(state, card_id: str) -> tuple[int, int]:
    card = state.cards[card_id]
    if not _is_battlefield(card):
        return (0, 0)
    if "Creature" not in effective_types(state, card):
        return (0, 0)
    p_bonus = 0
    t_bonus = 0
    for src_id, src, source_active in _continuous_sources(state):
        if not source_active:
            continue
        attached_p, attached_t, _, _ = _attached_effects(state, src, card)
        p_bonus += attached_p
        t_bonus += attached_t
        conditional_p, conditional_t, _, _ = _conditional_static_effects(state, src, card)
        p_bonus += conditional_p
        t_bonus += conditional_t
        counter_p, counter_t = _player_counter_pt_bonus(state, src, card)
        p_bonus += counter_p
        t_bonus += counter_t
        for scope, other_only, subject, p_delta, t_delta in _iter_pt_modifiers(src):
            if not _scope_controller(src.controller, scope, card.controller):
                continue
            if other_only and _other_creature_reference(src, subject) == card_id:
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
    total_p = 0
    total_t = 0
    subject = _self_stat_subject(source_card)
    for line in _static_oracle_text(source_card).splitlines():
        line = line.strip().rstrip('.').replace('\u2019', "'")
        scaled = re.fullmatch(subject + r' gets ([+-]\d+)/([+-]\d+) for each (.+)', line)
        variable = re.fullmatch(subject + r' gets ([+-])x/([+-])x, where x is (.+)', line)
        if scaled:
            counts = [_stat_resource_count(state, source_card, expression.replace(' card in ', ' cards in '))
                      for expression in scaled[3].split(' and each ')]
            if all(count is not None for count in counts):
                total_p += int(scaled[1]) * sum(counts)
                total_t += int(scaled[2]) * sum(counts)
        elif variable:
            count = (max(0, state.players[source_card.controller].life) if variable[3] == 'your life total'
                     else _stat_resource_count(state, source_card, variable[3]))
            if count is not None:
                total_p += count * (1 if variable[1] == '+' else -1)
                total_t += count * (1 if variable[2] == '+' else -1)
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


def _other_creature_reference(source, subject):
    # Attached creature text makes "other creatures" relative to its recipient,
    # not to the noncreature Aura/Equipment that carries the instruction.
    if (source.attached_to and subject == 'creatures'
            and re.search(r'\b(?:enchanted|equipped) creature\b', _static_oracle_text(source))):
        return source.attached_to
    return source.id


def _pt_setter_applies(state, source, target_id, scope, other_only, subject):
    target = state.cards[target_id]
    if not _is_battlefield(target):
        return False
    if scope == "attached":
        return (source.attached_to == target_id and "Creature" not in effective_types(state, source)
                and (subject == "permanent" or subject.title() in effective_types(state, target)))
    return ((scope == "all" or _scope_controller(source.controller, scope, target.controller))
            and not (other_only and source.id == target_id)
            and _subject_matches(state, target_id, subject))


@_static_parser
def _iter_keyword_grants(text):
    # Unconditional global grants use live membership and the source timestamp.
    for clause in re.split(r'[.\n]', text):
        match = re.fullmatch(r'(?:all )?(creatures) have (.+)', clause.strip())
        if match:
            granted = _attached_keywords(match[2])
            if granted:
                yield ('all', False, match[1], tuple(granted))
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
    parsed = _attached_keywords(text)
    if parsed is not None:
        return tuple(parsed)
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
    cache = query_cache(state)
    if cache is None:
        return _subject_match_result(state, card_id, subject)
    key = (_subject_match_result, card_id, subject)
    if key not in cache:
        cache[key] = _subject_match_result(state, card_id, subject)
    return cache[key]


def _subject_match_result(state, card_id: str, subject: str) -> bool:
    card = state.cards[card_id]
    s = (subject or "").strip().lower()
    type_nouns = _STATIC_TYPE_NOUNS
    if s in type_nouns:
        return type_nouns[s] in effective_types(state, card)
    if s == "permanents":
        return _is_battlefield(card) and bool(set(effective_types(state, card)) & set(type_nouns.values()))
    if s == "tokens":
        return is_token_card(card)
    if s == "creature tokens":
        return "Creature" in effective_types(state, card) and is_token_card(card)
    if s.endswith(" creatures"):
        if "Creature" not in effective_types(state, card):
            return False
        from rules_engine.colors import card_color_symbols
        colors = card_color_symbols(card, state)
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
                matched = word.title() in effective_types(state, card)
            elif word in {"legendary", "snow"}:
                matched = word in front_types
            else:
                matched = _has_subtype(card, word, state=state)
            return not matched if negative else matched

        return all(matches(word) for word in s.removesuffix(" creatures").split())
    return any(_has_subtype(card, singular, state=state) for singular in creature_subtype_candidates(s))


def _has_subtype(card, subtype: str, *, state=None) -> bool:
    types = effective_types(state, card) if state is not None else (getattr(card, "types", []) or [])
    if "Creature" not in types:
        return False
    from rules_engine.library_permissions import creature_types
    tokens = creature_types(card, state)
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
    if match := re.fullmatch(r'(basic|nonbasic) lands?', s):
        if "Land" not in (getattr(card, "types", []) or []):
            return False
        front = re.split(r'\s[\u2014-]\s', (getattr(card, "type_line", "") or "").split("//", 1)[0], maxsplit=1)[0]
        basic = "Basic" in front.split()
        return basic if match[1] == "basic" else not basic
    type_map = {kind.lower(): kind for kind in CARD_TYPES}
    if s in type_map:
        return type_map[s] in (getattr(card, "types", []) or [])
    if s.endswith("s") and s[:-1] in type_map:
        return type_map[s[:-1]] in (getattr(card, "types", []) or [])
    if "Creature" not in (getattr(card, "types", []) or []):
        return False
    if s.endswith("s"):
        s = s[:-1]
    return _has_subtype(card, s)


def _battlefield_card_matches_selector(card, selector: str, *, state=None) -> bool:
    if not card:
        return False
    s = selector.strip().lower()
    types = effective_types(state, card) if state is not None else (getattr(card, 'types', []) or [])
    type_map = {word: kind for kind in CARD_TYPES for word in [kind.lower(), kind.lower() + 's']}
    if s in type_map:
        return type_map[s] in types
    if s in {"creature", "creatures"}:
        return "Creature" in types
    if s in {"artifact creature", "artifact creatures"}:
        return "Creature" in types and "Artifact" in types
    if s.endswith(" creatures"):
        tribe = s.replace(" creatures", "").strip()
        return _has_subtype(card, tribe, state=state)
    if s.endswith("s"):
        s = s[:-1]
    return _has_subtype(card, s, state=state)


@scoped_query
def _continuous_sources(state):
    """Reuse ordered source activity only inside immutable rules queries."""
    losses = _printed_ability_loss_sources(state)
    return tuple((cid, source, not printed_abilities_suppressed(state, cid, losses=losses))
                 for cid in _all_battlefield_ids(state)
                 if (source := state.cards.get(cid)))


@scoped_query
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


@scoped_query
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
    from rules_engine.combat_constraints import combat_rule_view
    combat_view = combat_rule_view(state, card_id)
    card = state.cards[card_id]
    ability_losses = _printed_ability_loss_sources(state)
    trace: list[dict[str, Any]] = []
    applied_layers: list[tuple[tuple[int, int, int, int, int, str], dict[str, Any]]] = []
    layer_index = 0
    if _is_battlefield(card):
        from rules_engine.type_effects import active_type_effects, devotion_type_condition
        from rules_engine.devotion import devotion_count
        condition = devotion_type_condition(card.oracle_text, card.name)
        if condition is not None and devotion_count(state, card.controller, condition[0]) < condition[1]:
            key = _continuous_layer_sort_key(state, card_id, 'type-remove:Creature')
            applied_layers.append((key, {
                'source_id': card_id, 'source_name': card.name, 'target_id': card_id,
                'layer': 'type-remove:Creature', 'effect_timestamp': effect_timestamp(card),
                'timestamp_origin': 'battlefield', 'devotion_colors': list(condition[0]),
                'devotion_threshold': condition[1],
            }))
        for effect in active_type_effects(card):
            layer = 'type-add:' + ','.join(effect['types'])
            key = _continuous_layer_sort_key(state, card_id, layer)
            applied_layers.append(((key[0], key[1], effect['timestamp'], *key[3:]), {
                'source_id': effect.get('source_card_id'), 'source_name': effect.get('source_name'),
                'target_id': card_id, 'layer': layer, 'effect_timestamp': effect['timestamp'],
                'timestamp_origin': effect['timestamp_origin'], 'until_end_of_turn': effect['until_end_of_turn'],
            }))
        for effect in _resolved_base_stat_effects(card):
            key = _continuous_layer_sort_key(state, card_id, 'pt-set')
            applied_layers.append(((key[0], key[1], effect['timestamp'], *key[3:]), {
                'source_id': effect.get('source_card_id'), 'source_name': effect.get('source_name'),
                'target_id': card_id, 'layer': 'pt-set', 'effect_timestamp': effect['timestamp'],
                'timestamp_origin': effect['timestamp_origin'], 'until_end_of_turn': effect['until_end_of_turn'],
                'base_power': effect['power'], 'base_toughness': effect['toughness'],
            }))
        for effect in _resolved_keyword_modifiers(card):
            label = 'all-abilities' if effect['keyword'] == 'all abilities' else effect['keyword']
            layer = f"keyword-{'remove' if effect['operation'] == 'remove' else 'grant'}:{label}"
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
        if printed_abilities_suppressed(state, src_id, losses=ability_losses):
            continued = _ability_layer_continuation_source(state, src)
            layer_entries = _source_continuous_layer_entries(state, continued, card_id) if continued else []
            from rules_engine.basic_land_layer import prior_layer_abilities_lost
            if not continued and not prior_layer_abilities_lost(state, src):
                layer_entries = [entry for entry in _source_continuous_layer_entries(state, src, card_id)
                                 if entry['layer'] == 'keyword-remove:all-abilities']
        else:
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
        "combat_constraints": combat_view['active'],
        "unsupported_combat_clauses": combat_view['unsupported'],
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
        "unsupported_conditional_static_clauses": [
            {"source_id": cid, "source_name": state.cards[cid].name, "clause": clause}
            for cid in _all_battlefield_ids(state)
            for clause in _conditional_static_effects(state, state.cards[cid], card)[3]
        ],
    }


def _source_continuous_layer_entries(state, source_card, target_card_id: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not _is_battlefield(state.cards[target_card_id]):
        return entries
    target = state.cards[target_card_id]
    conditional_p, conditional_t, conditional_keywords, _ = _conditional_static_effects(state, source_card, target)
    if conditional_p or conditional_t:
        entries.append({'layer': f'pt-mod:{conditional_p}/{conditional_t}', 'conditional': True})
    if conditional_keywords:
        entries.append({'layer': f"keyword-grant:{','.join(conditional_keywords)}", 'conditional': True})
    counter_p, counter_t = _player_counter_pt_bonus(state, source_card, target)
    if counter_p or counter_t:
        entries.append({"layer": f"pt-mod:{counter_p}/{counter_t}"})
    attached_p, attached_t, attached_keywords, _ = _attached_effects(state, source_card, target)
    if attached_p or attached_t:
        entries.append({"layer": f"pt-mod:{attached_p}/{attached_t}"})
    if attached_keywords:
        entries.append({"layer": f"keyword-grant:{','.join(attached_keywords)}"})
    for scope, other_only, subject, p_delta, t_delta in _iter_pt_modifiers(source_card):
        if _scope_controller(source_card.controller, scope, target.controller) and not (other_only and _other_creature_reference(source_card, subject) == target_card_id) and _subject_matches(state, target_card_id, subject):
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
