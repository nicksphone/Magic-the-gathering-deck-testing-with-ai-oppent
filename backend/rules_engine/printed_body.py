"""Shared complete printed-body contracts for admission and coverage."""
from copy import copy
import re


def normalized_body(text, family):
    """Remove only a reminder whose wording agrees with the compiled ability."""
    from rules_engine.oracle_text import without_reminder_text
    raw = (text or '').strip()
    normalized = without_reminder_text(raw).strip()
    if family == 'kicker' and '(' in raw:
        lines = raw.splitlines()
        header = re.fullmatch(
            r'(Kicker ((?:\{[WUBRGC]\})+) and/or ((?:\{[WUBRGC]\})+)) \(([^()]*)\)',
            lines[0], re.I)
        if (header is None or header[4] != 'You may pay an additional ' + header[2]
                + ' and/or ' + header[3] + ' as you cast this spell.'
                or any('(' in line or ')' in line for line in lines[1:])):
            return None
        return '\n'.join([header[1], *lines[1:]])
    if family == 'turn_protection' and '(' in raw:
        from rules_engine.turn_spell_protection import compile_instruction
        compiled = compile_instruction(normalized)
        if compiled is None or compiled[0] != 'effect_sequence':
            return None
        colors = compiled[1]['effects'][-1]['payload']['colors']
        reminder = "You and they can't be the targets of " + ' or '.join(colors) \
            + ' spells or abilities your opponents control.'
        if ' '.join(raw.split()) != ' '.join(normalized.split()) + ' (' + reminder + ')':
            return None
        return normalized
    return None if '(' in raw or ')' in raw else raw


def normalized_card(card, family):
    text = normalized_body(card.oracle_text, family)
    if text is None:
        return None
    result = copy(card)
    result.oracle_text = text
    return result


def complete_bestow_surface(card):
    from rules_engine.bestow import bestow_cost
    from rules_engine.attached_token_payment import compile_instruction, KEY
    from rules_engine.continuous import ATTACHED_PT_RE, _attached_keywords
    if card is None or not {'Creature', 'Enchantment'}.issubset(card.types):
        return False
    lines = [line.strip() for line in card.oracle_text.splitlines()]
    price = bestow_cost(card)
    if (len(lines) != 3 or price is None
            or not re.fullmatch(r'(?:\{(?:\d{1,6}|[WUBRGC])\})+', price)
            or not re.fullmatch('Bestow ' + re.escape(price), lines[0], re.I)):
        return False
    attached = ATTACHED_PT_RE.fullmatch(lines[1].lower().removesuffix('.'))
    if (attached is None or attached[1] != 'creature' or attached[4] is not None
            or _attached_keywords(attached[5]) is None):
        return False
    compiled = compile_instruction(card, card.oracle_text)
    return compiled is not None and compiled[0] == KEY


def complete_keyword_surface(card, family):
    if card is None:
        return False
    if family == 'turn_protection':
        from rules_engine.turn_spell_protection import compile_instruction
        compiled = compile_instruction(card.oracle_text)
        return ('Instant' in card.types and compiled is not None
                and compiled[0] == 'effect_sequence')
    from rules_engine.exchange_energy import compile_instruction, KEY
    from rules_engine.protection import hexproof_variants
    lines = card.oracle_text.splitlines()
    compiled = compile_instruction(card, 1)
    return ('Creature' in card.types and len(lines) == 2
            and compiled is not None and compiled[0] == KEY
            and bool(hexproof_variants(lines[0].partition(', ')[2])))


def printed_body_gaps(card):
    """Recognized complete families must account for the entire selected text."""
    text = card.oracle_text or ''
    types = set(card.types or [])
    if 'Planeswalker' in types:
        from rules_engine.closed_loyalty import compile_body
        return (() if compile_body(text, card.name) is not None
                else ('unsupported complete loyalty body',))
    if types.intersection({'Instant', 'Sorcery'}):
        from rules_engine.oracle_effects import compile_additional_cost_draw_instruction
        cost_draw = compile_additional_cost_draw_instruction(text, card.name)
        if cost_draw is not None:
            return (() if cost_draw[0] != 'noop'
                    else ('unsupported complete additional-cost draw body',))
    from rules_engine.turn_spell_protection import CANDIDATE
    if types.intersection({'Instant', 'Sorcery'}) and CANDIDATE.match(text.strip()):
        from rules_engine.turn_spell_protection import compile_instruction
        family = 'turn_protection'
        body = normalized_body(text, family)
        compiled = compile_instruction(body) if body is not None else None
        valid = compiled is not None and compiled[0] == 'effect_sequence'
    elif re.search(r'^kicker .+ and/or ', text, re.I | re.M) and 'Creature' in types:
        from rules_engine.kicker import paired_permanent_kicker
        family = 'paired kicker'
        view = normalized_card(card, 'kicker')
        valid = view is not None and paired_permanent_kicker(view) is not None
    elif re.search(r'you may pay .+ if this permanent is attached', text, re.I):
        family = 'attached payment'
        view = normalized_card(card, 'bestow')
        # The cast view of a bestowed card retains its printed creature types here.
        if view is not None and getattr(card, 'bestow_characteristics', None):
            view.types = card.bestow_characteristics['types']
        valid = complete_bestow_surface(view)
    elif re.search(r'exchange control of this (?:creature|permanent)', text, re.I):
        from rules_engine.exchange_energy import compile_instruction, KEY
        family = 'entry exchange'
        view = normalized_card(card, 'exchange')
        compiled = compile_instruction(view, 1) if view is not None else None
        valid = compiled is not None and compiled[0] == KEY
    elif (re.search(r'When this (?:creature|permanent) enters(?: the battlefield)?, choose one', text, re.I)
          and 'counters' in text.lower() and 'for as long as this' in text.lower()):
        from rules_engine.modal_entry import compile_instruction
        family = 'modal counter prohibition'
        valid = compile_instruction(text) is not None
    else:
        return ()
    return () if valid else ('unsupported complete ' + family + ' body',)
