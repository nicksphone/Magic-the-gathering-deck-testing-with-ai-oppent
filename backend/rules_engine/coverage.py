from __future__ import annotations

import re


_UNSUPPORTED_RESOLUTION_PATTERNS = (
    ('extra-turn scheduling', re.compile(r'\b(?:take|takes) (?:an?|one|two|three|\d+) extra turns?\b', re.I)),
    ('extra-phase scheduling', re.compile(r'\badditional (?:combat|main) phase\b', re.I)),
    ('turn-ending procedure', re.compile(r'\bend the turn\b', re.I)),
    ('player-turn control', re.compile(r'\byou control target player during\b', re.I)),
    ('top-library reorder and optional shuffle', re.compile(
        r'\bput them back in any order\.\s*you may shuffle\b', re.I)),
    ('top-library reorder procedure', re.compile(
        r'\blook at the top\b.+?\bput them back in any order\b', re.I | re.S)),
)


def unsupported_resolution_clauses(text: str) -> list[str]:
    """Bounded observed gaps, not proof that other clauses are executable."""
    from rules_engine.oracle_text import without_reminder_text
    text = without_reminder_text(text or '')
    from rules_engine.turn_scheduler import instruction
    if instruction(text):
        return []
    # A whole activated schema may follow its printed cost on a permanent.
    text = '\n'.join(line for line in text.splitlines()
                     if not (':' in line and instruction(line.split(':', 1)[1])))
    from rules_engine.library_reorder import reorder_clause
    return [name for name, pattern in _UNSUPPORTED_RESOLUTION_PATTERNS if pattern.search(text)
            and not (name.startswith('top-library reorder') and reorder_clause(text))]


_UNSUPPORTED_PATTERNS = (
    ('controller-linked damage targets', re.compile(
        r'damage to target (?:player(?: or planeswalker)?|planeswalker)[^.]*'
        r"target creature that (?:player|planeswalker|player or that planeswalker's controller) controls",
        re.IGNORECASE)),
    ('conditional land-entry damage', re.compile(
        r'landfall\s*[^\w\s]*\s*if you had a land enter the battlefield under your control this turn,'
        r'[^.]*damage[^.]*instead', re.IGNORECASE)),
    ('independent target-instance fidelity', re.compile(
        r'target creature gets [+-]\d+/[+-]\d+ until end of turn\.'
        r'\s*target creature gets [+-]\d+/[+-]\d+ until end of turn', re.IGNORECASE)),
    ('bestow', re.compile(r'\bbestow\b', re.IGNORECASE)),
    ('blocking assignment controller fidelity', re.compile(r'(?:attacking|defending) player chooses how .*blocks', re.IGNORECASE)),
    ('tap/untap choice fidelity', re.compile(r'\btap or untap\b',re.IGNORECASE)),
    ("scry replacement fidelity", re.compile(r'if .+scry.+instead', re.IGNORECASE)),
    ("scry trigger fidelity", re.compile(r'whenever .+scry', re.IGNORECASE)),
    ("dynamic scry", re.compile(r'\bscry x\b', re.IGNORECASE)),
    ("keyword counter variant fidelity", re.compile(r'\bhexproof from\b|\btrample over planeswalkers\b', re.IGNORECASE)),
    ("conditional keyword trigger grants", re.compile(r'as long as [^.]+(?:exalted|decayed)|(?:exalted|decayed) as long as', re.IGNORECASE)),
    ("shield competing prevention fidelity", re.compile(r"\bshield counters?\b", re.IGNORECASE)),
    ("proliferate event replacement", re.compile(r"if you would proliferate", re.IGNORECASE)),
    ("conditional proliferation", re.compile(r"if you do, proliferate", re.IGNORECASE)),
    ("read ahead entry route fidelity", re.compile(r"\bread ahead\b", re.IGNORECASE)),
    ("phasing", re.compile(r"\bphases? (?:in|out)\b|\bphasing\b", re.IGNORECASE)),
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


def combat_coverage_details(oracle_text: str, card_faces: list[dict] | None = None, *, card_name: str = '') -> list[dict]:
    from rules_engine.combat_constraints import combat_clause_coverage
    variants = [(None, card_name, oracle_text or ''),
                *((index, str(face.get('name') or card_name), str(face.get('oracle_text') or ''))
                  for index, face in enumerate(card_faces or []) if isinstance(face, dict))]
    return [{**row, 'face_index': index, 'face_name': name}
            for index, name, text in variants for row in combat_clause_coverage(text, name)]


def static_coverage_details(oracle_text: str, card_faces: list[dict] | None = None, *, card_name: str = '') -> list[dict]:
    from rules_engine.continuous import conditional_static_clause_coverage
    variants = [(None, card_name, oracle_text or ''),
                *((index, str(face.get('name') or card_name), str(face.get('oracle_text') or ''))
                  for index, face in enumerate(card_faces or []) if isinstance(face, dict))]
    return [{**row, 'face_index': index, 'face_name': name}
            for index, name, text in variants for row in conditional_static_clause_coverage(text, name)]


def known_unsupported_mechanics(oracle_text: str, card_faces: list[dict] | None = None, *, card_name: str = '') -> list[str]:
    """Known gaps only; an empty result is not rules certification."""
    texts = [oracle_text or "", *(str(face.get("oracle_text") or "") for face in card_faces or [] if isinstance(face, dict))]
    out = [name for name, pattern in _UNSUPPORTED_PATTERNS if any(pattern.search(value) for value in texts)]
    out.extend(gap for value in texts for gap in unsupported_resolution_clauses(value))
    from rules_engine.affinity import affinity_clauses
    if any(affinity_clauses(text)[2] for text in texts):
        out.append('unsupported affinity clause')
    from rules_engine.kicker import kicked_cast_clauses
    from rules_engine.oracle_text import without_reminder_text
    from rules_engine.foretell import PRINTED, GRANT, MODIFIER, FIRST, spell_variants, created_clauses
    for text in texts:
        created_lines = {clause['line'] for clause in created_clauses(text, card_name)}
        for line in without_reminder_text(text).splitlines():
            if not re.search(r'\bforet(?:ell|old|elling)\b', line, re.I):
                continue
            reward = re.fullmatch(r'whenever you foretell a card, (?:this creature|' + re.escape(card_name)
                                  + r') gets [+-]\d+/[+-]\d+ until end of turn\.', line.strip(), re.I)
            if not (spell_variants(text) or PRINTED.fullmatch(line.strip()) or GRANT.fullmatch(line.strip())
                    or MODIFIER.fullmatch(line.strip()) or FIRST.fullmatch(line.strip()) or reward
                    or line.strip() in created_lines):
                out.append('foretell-related effect fidelity')
    from rules_engine.devotion import devotion_instruction, devotion_mana_instruction
    from rules_engine.type_effects import devotion_type_condition
    variants = [(card_name, oracle_text or ''),
                *((str(face.get('name') or card_name), str(face.get('oracle_text') or ''))
                  for face in card_faces or [] if isinstance(face, dict))]
    for name, text in variants:
        for line in without_reminder_text(text).lower().splitlines():
            if 'devotion to' not in line:
                continue
            instruction = re.sub(r'^when (?:this creature|' + re.escape(name.lower())
                                 + r') enters(?: the battlefield)?, ', '', line.strip())
            mana_instruction = re.sub(r'^[^:]+:\s*', '', line.strip())
            if (devotion_instruction(instruction, name) is None and devotion_type_condition(line.strip(), name) is None
                    and devotion_mana_instruction(mana_instruction) is None):
                out.append('unsupported devotion instruction')
    for text in texts:
        clauses = {item['clause'].lower() for item in kicked_cast_clauses(text)}
        if any(re.search(r'^whenever\b.*\bkicked\b', line.strip(), re.I)
               and line.strip().lower() not in clauses
               for line in without_reminder_text(text).splitlines()):
            out.append('kicked-cast trigger fidelity')
            break
    if 'kicker' in out:
        from rules_engine.kicker import kicker_surfaces, permanent_kicker
        kicker_texts = [text for text in texts if re.search(r'\bkicker\b', text, re.I)]
        if all(kicker_surfaces(text) is not None or permanent_kicker(text) is not None for text in kicker_texts):
            out.remove('kicker')
    from rules_engine.activation_modifiers import activation_modifier_gaps
    from rules_engine.combat_constraints import static_clauses
    from rules_engine.hooks import spell_cost_modifier
    if any(re.search(r'\b(?:white|blue|black|red|green|colorless)\b.*spells?.*cost.*to cast', clause)
           and spell_cost_modifier(clause) is None
           for text in texts for clause in static_clauses(text)):
        out.append('unsupported color-qualified spell cost')
    variants = [(card_name, oracle_text or ''),
                *((str(face.get('name') or card_name), str(face.get('oracle_text') or ''))
                  for face in card_faces or [] if isinstance(face, dict))]
    from rules_engine.spell_cost_clauses import spell_additional_costs
    from rules_engine.conditional_instructions import instruction_gaps
    for name, text in variants:
        out.extend(instruction_gaps(text, name))
    if any(spell_additional_costs(text, name) is None for name, text in variants):
        out.append('unsupported spell additional cost')
    from rules_engine.spell_cost_clauses import resource_x_effect_gaps
    for name, text in variants:
        if any(branch.get('discard_x') for branch in spell_additional_costs(text, name) or []):
            out.extend(resource_x_effect_gaps(text))
    from rules_engine.linked_discard import linked_discard_gaps
    for _, text in variants:
        out.extend(linked_discard_gaps(text))
    from rules_engine.kicker import kicker_components, kicker_surfaces, permanent_kicker
    for name, text in variants:
        surfaces = kicker_surfaces(text)
        permanent = permanent_kicker(text) if surfaces is None else None
        price = surfaces[0] if surfaces else permanent['price'] if permanent else None
        extra = kicker_components(price) if price is not None else None
        if extra and extra.get('sacrifice_creatures'):
            branches = spell_additional_costs(text, name) or []
            if any(branch.get('sacrifice_creatures') and branch.get('sacrifice_kind') != extra['sacrifice_kind']
                   for branch in branches):
                out.append('unsupported mixed sacrifice cost')
                break
    if any(activation_modifier_gaps(text, name) for name, text in variants):
        out.append('activation cost modifiers')
    if 'domain' in out:
        from rules_engine.combat_payments import parse_attack_tax
        from rules_engine.oracle_text import without_reminder_text
        domain_clauses = [line.lower().strip().rstrip('.') for text in texts
                          for line in without_reminder_text(text).splitlines()
                          if re.match(r'domain\s*[—–-]', line.strip(), re.I)]
        if domain_clauses and all(parse_attack_tax(line) and parse_attack_tax(line)['scaling'] == 'domain' for line in domain_clauses):
            out.remove('domain')
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
    from rules_engine.scry import surveil_payoff, cast_surveillance_clause
    for text in texts:
        stripped = without_reminder_text(text).lower()
        if re.search(r'\bsurveil x\b', stripped):
            out.append('dynamic surveil')
        if re.search(r'(?:additional .+ cards? .+surveil|if .+surveil.+instead)', stripped):
            out.append('surveil modification/replacement fidelity')
        if any('whenever' in line and 'surveil' in line and surveil_payoff(line) is None and cast_surveillance_clause(line) is None
               for line in stripped.splitlines()):
            out.append('unsupported surveil trigger clause')
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
    for row in combat_coverage_details(oracle_text, card_faces, card_name=card_name):
        out.extend(reason for reason in row['reasons'] if reason not in out)
    for row in static_coverage_details(oracle_text, card_faces, card_name=card_name):
        out.extend(reason for reason in row['reasons'] if reason not in out)
    from rules_engine.graveyard_permissions import permission_gaps
    for name, text in variants:
        out.extend(permission_gaps(text, name))
    return list(dict.fromkeys(out))


def deck_pair_coverage(deck_a: list[dict], deck_b: list[dict]) -> dict:
    """Report known gaps without implying certification for the remaining cards."""
    return {
        "status": "exploratory",
        "known_unsupported_cards": [
            {"deck": label, "card_name": item.get("card_name", ""), "mechanics": mechanics,
             **({'combat_clause_gaps': details} if (details := combat_coverage_details(
                 str(item.get('oracle_text') or ''), item.get('card_faces'), card_name=str(item.get('card_name') or ''))) else {}),
             **({'static_clause_gaps': details} if (details := static_coverage_details(
                 str(item.get('oracle_text') or ''), item.get('card_faces'), card_name=str(item.get('card_name') or ''))) else {})}
            for label, deck in (("A", deck_a), ("B", deck_b))
            for item in deck
            if (mechanics := known_unsupported_mechanics(str(item.get("oracle_text") or ""), item.get("card_faces"), card_name=str(item.get('card_name') or '')))
        ],
    }
