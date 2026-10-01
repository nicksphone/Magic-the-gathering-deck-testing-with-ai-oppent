from __future__ import annotations

import re


_UNSUPPORTED_PATTERNS = (
    ("reconfigure", re.compile(r"\breconfigure\b", re.IGNORECASE)),
    ("fortify", re.compile(r"\bfortify\b", re.IGNORECASE)),
    ("full ability suppression", re.compile(r"\blose(?:s)? all abilities\b", re.IGNORECASE)),
    ("bands with other", re.compile(r"\bbands with other\b", re.IGNORECASE)),
    ("fuse", re.compile(r"\bfuse\b", re.IGNORECASE)),
    ("morph", re.compile(r"\bmorph\b", re.IGNORECASE)),
    ("manifest", re.compile(r"\bmanifest(?:ed|ing)?\b", re.IGNORECASE)),
    ("suspend", re.compile(r"\bsuspend(?:ed|ing)?\b", re.IGNORECASE)),
    ("mutate", re.compile(r"\bmutat(?:e|ed|ing)\b", re.IGNORECASE)),
    ("craft", re.compile(r"\bcraft\b", re.IGNORECASE)),
    ("discover", re.compile(r"\bdiscover\b", re.IGNORECASE)),
    ("kicker", re.compile(r"\bkicker\b", re.IGNORECASE)),
    ("multikicker", re.compile(r"\bmultikicker\b", re.IGNORECASE)),
    ("domain", re.compile(r"\bdomain\s*[—-]", re.IGNORECASE)),
    ("incubate", re.compile(r"\bincubat(?:e|es|ed|ing)\b", re.IGNORECASE)),
    ("copy-layer fidelity", re.compile(r"\bbecomes a copy of (?:that|the chosen|a chosen) card\b", re.IGNORECASE)),
)


def known_unsupported_mechanics(oracle_text: str, card_faces: list[dict] | None = None) -> list[str]:
    """Known gaps only; an empty result is not rules certification."""
    texts = [oracle_text or "", *(str(face.get("oracle_text") or "") for face in card_faces or [] if isinstance(face, dict))]
    out = [name for name, pattern in _UNSUPPORTED_PATTERNS if any(pattern.search(value) for value in texts)]
    from rules_engine.attachments import enchant_restriction
    if any(re.search(r"^enchant ", value, re.I | re.M) and enchant_restriction(value) is None for value in texts):
        out.append("unsupported enchant restriction")
    from rules_engine.ward import unsupported_ward_costs
    if any(list(unsupported_ward_costs(text)) for text in texts):
        out.append("unsupported ward cost")
    from rules_engine.player_counters import gain_clause
    from rules_engine.counter_placement import unsupported_counter_prohibitions
    if any(unsupported_counter_prohibitions(text) for text in texts):
        out.append('unsupported counter prohibition')
    from rules_engine.oracle_text import without_reminder_text
    if any(re.search(r'\byou get (?:an?|\d+) [a-z-]+ counters?\b', line, re.I)
           and gain_clause(line) is None
           for text in texts for line in without_reminder_text(text).splitlines()):
        out.append('unsupported player-counter gain clause')
    if any(re.search(r'\bif .+counters?.+(?:player|yourself|you (?:would )?get)\b', text, re.I) for text in texts):
        out.append('player-counter replacement fidelity')
    from rules_engine.counter_replacements import counter_modifier
    replacement_lines = [line for text in texts for line in without_reminder_text(text).splitlines()
                         if re.match(r'if\b', line, re.I) and re.search(r'\bcounters?\b.*instead', line, re.I)]
    if replacement_lines:
        out.append('counter replacement route fidelity')
        if any(counter_modifier(line) is None for line in replacement_lines):
            out.append('unsupported counter replacement clause')
    from rules_engine.continuous import PLAYER_COUNTER_PT_RE, SELF_PLAYER_COUNTER_PT_RE
    from rules_engine.player_counters import PLAYER_COUNT_RE
    from rules_engine.ward import DYNAMIC_WARD_RE, parse_ward_cost
    for text in texts:
        for line in without_reminder_text(text).lower().splitlines():
            line = line.strip().rstrip('.')
            if not re.search(r'\b[a-z-]+ counters? you have\b', line):
                continue
            supported = (PLAYER_COUNTER_PT_RE.fullmatch(line) or SELF_PLAYER_COUNTER_PT_RE.fullmatch(line)
                         or re.fullmatch(r"this creature's power and toughness are each equal to the " + PLAYER_COUNT_RE, line)
                         or any(parse_ward_cost(match[1]) for match in DYNAMIC_WARD_RE.finditer(line)))
            if not supported:
                out.append('unsupported player-counter dependent clause')
                break
        if 'unsupported player-counter dependent clause' in out:
            break
    return out


def deck_pair_coverage(deck_a: list[dict], deck_b: list[dict]) -> dict:
    """Report known gaps without implying certification for the remaining cards."""
    return {
        "status": "exploratory",
        "known_unsupported_cards": [
            {"deck": label, "card_name": item.get("card_name", ""), "mechanics": mechanics}
            for label, deck in (("A", deck_a), ("B", deck_b))
            for item in deck
            if (mechanics := known_unsupported_mechanics(str(item.get("oracle_text") or ""), item.get("card_faces")))
        ],
    }
