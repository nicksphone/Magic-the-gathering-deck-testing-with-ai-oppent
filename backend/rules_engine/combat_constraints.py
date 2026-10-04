"""Pure, condition-aware supported static combat clauses and their provenance."""
from rules_engine.type_effects import effective_types
import re
from functools import lru_cache

from game_state.state import Zone
from rules_engine.oracle_text import without_reminder_text

from rules_engine.static_conditions import NUMBERS, number, parse_static_condition, evaluate_static_condition, static_clause_components

BODY = re.compile(r"^(?:(?:can't|cannot) (?:attack|block|be blocked)|can block|attacks? each combat|blocks? each combat|must (?:attack|block))\b")


def supported_body(text):
    return bool(re.fullmatch(
        r"(?:(?:can't|cannot) (?:attack(?: or block)?|block)(?: alone| artifact creatures)?"
        r"|(?:can't|cannot) be blocked(?: by creatures with power \d+ or (?:less|greater)"
        r"| except by (?:\d+|one|two|three|four|five|six|seven|eight|nine|ten) or more creatures)?"
        r"|can block (?:any number of creatures|an additional creature each combat"
        r"|(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten) additional creatures each combat"
        r"|only creatures with flying)"
        r"|(?:attacks?|blocks?) each combat if able|must (?:attack|block) each combat if able)", text))
@lru_cache(maxsize=4096)
def static_clauses(oracle):
    lines = []
    for line in without_reminder_text(oracle or '').lower().splitlines():
        line = line.strip()
        if re.match(r'^(?:when|whenever|at the beginning|during)\b', line) or ':' in line or 'until end of turn' in line:
            continue
        line = re.sub(r'"[^"]*"|\u201c[^\u201d]*\u201d', '""', line)
        lines.extend(component for part in re.split(r'\.\s+', line) if part.strip(' .')
                     for component in static_clause_components(part.strip(' .')))
    return tuple(lines)


def _condition(state, source, target, text):
    return evaluate_static_condition(state, source, target, text)


def conditional_clause(clause):
    prefix = re.fullmatch(r'(?:as long as|if) (.+?), (.+)', clause)
    suffix = re.fullmatch(r'(.+?) (as long as|unless) (.+)', clause)
    if prefix:
        return prefix[2], prefix[1], False
    if suffix:
        return suffix[1], suffix[3], suffix[2] == 'unless'
    return clause, None, False


def combat_clause_coverage(oracle, card_name=''):
    """Known unsupported static combat clauses, without fabricating a game state."""
    body_search = re.compile(BODY.pattern.removeprefix('^') + r'|\bcan (?:attack|be blocked)\b')
    records = []
    from rules_engine.combat_payments import temporary_combat_tax
    for line in without_reminder_text(oracle or '').lower().splitlines():
        text = line.split(':', 1)[-1].strip().rstrip('.')
        if text.startswith('this turn, ') and re.search(r"creatures can't (?:attack|block) unless", text) and not temporary_combat_tax(text):
            records.append({'clause': text, 'reasons': ['unsupported combat payment']})
    previous = None
    for clause in static_clauses(oracle):
        if clause.startswith('this turn, ') and re.search(r"creatures can't (?:attack|block) unless", clause):
            continue  # The resolving-instruction coverage above owns this clause.
        if clause.startswith('otherwise, '):
            body, condition, _ = clause.removeprefix('otherwise, '), previous, False
            missing_condition = previous is None
        else:
            body, condition, _ = conditional_clause(clause)
            previous = condition
            missing_condition = False
        from rules_engine.declaration_limits import parse_declaration_limit
        limit = parse_declaration_limit(body)
        if limit and condition is None and not missing_condition:
            continue
        from rules_engine.combat_payments import parse_static_combat_tax
        from rules_engine.combat_requirements import parse_target_block_requirement
        if parse_static_combat_tax(clause, card_name) or parse_target_block_requirement(clause, card_name):
            continue
        if re.search(r'all .+? able to block|must be blocked', clause):
            records.append({'clause': clause, 'reasons': ['unsupported targeted block requirement']})
            continue
        match = body_search.search(body)
        if match is None:
            continue
        subject, recipient = body[:match.start()].strip(), body[match.start():]
        reasons = []
        if condition and (parse_static_condition(condition, card_name) is None or limit) or missing_condition:
            reasons.append('unsupported combat condition')
        if re.search(r'\bunless\b.+\bpay(?:s)?\b', clause):
            reasons.append('unsupported combat payment')
        if not supported_body(recipient):
            reasons.append('unsupported combat clause')
        if not _supported_combat_subject(subject, card_name):
            reasons.append('unsupported combat subject')
        if reasons:
            records.append({'clause': clause, 'reasons': reasons})
    return records


def _supported_combat_subject(subject, card_name):
    if subject in {'', 'it', 'cardname', 'this creature', 'this permanent', card_name.lower()}:
        return True
    if re.fullmatch(r'(?:enchanted|equipped|fortified) (?:creature|permanent|artifact|enchantment|land|planeswalker|battle)', subject):
        return True
    from rules_engine.card_types import CREATURE_SUBTYPES
    from rules_engine.static_conditions import COLORS, TYPES
    subject = re.sub(r'^(?:other |each |all )', '', subject)
    subject = re.sub(r' (?:you control|your opponents control)$', '', subject)
    if subject.endswith(' creature'):
        subject += 's'
    if subject in {'creature', 'creatures', 'permanent', 'permanents', 'tokens', 'creature tokens'}:
        return True
    if subject.endswith(' creatures'):
        allowed = set(COLORS) | TYPES | {'token', 'legendary', 'snow', 'colorless'} | set(CREATURE_SUBTYPES)
        return all(word.removeprefix('non').lstrip('-') in allowed
                   for word in subject.removesuffix(' creatures').split())
    # Use the same recognized plural-subtype vocabulary as global statics.
    from rules_engine.card_types import creature_subtype_candidates
    return any(candidate in CREATURE_SUBTYPES for candidate in creature_subtype_candidates(subject))


def _recipient_body(state, source, target, text):
    self_subject = rf'(?:this (?:creature|permanent)|cardname|{re.escape(source.name.lower())}) '
    if source.id == target.id:
        match = re.match(self_subject, text)
        if match:
            return text[match.end():]
        if BODY.match(text):
            return text
    if getattr(source, 'attached_to', None) == target.id and 'Creature' not in effective_types(state, source):
        match = re.match(r'(?:enchanted|equipped|fortified) (?:creature|permanent|artifact|enchantment|land|planeswalker|battle) |it ', text)
        if match:
            return text[match.end():]
    if re.match(r'(?:this|it|enchanted|equipped|fortified)\b', text):
        return None
    global_subject = re.fullmatch(r'(other |all )?(?:each )?([a-z -]+?) (you control|your opponents control)?\s*('
                                  r"(?:(?:can't|cannot) (?:attack|block|be blocked)|can block|attacks? each combat|blocks? each combat|must (?:attack|block))\b.*)", text)
    if global_subject and BODY.match(global_subject[4]):
        from rules_engine.continuous import _scope_controller, _subject_matches
        scope = global_subject[3]
        if (global_subject[1] != 'other ' or source.id != target.id) and (scope is None or _scope_controller(source.controller, scope, target.controller)):
            subject = global_subject[2]
            if subject.endswith('creature') or subject.endswith('permanent'):
                subject += 's'
            if _subject_matches(state, target.id, subject):
                return global_subject[4]
    return None


def combat_rule_view(state, card_id):
    from rules_engine.continuous import printed_abilities_suppressed, _printed_ability_loss_sources
    target = state.cards[card_id]
    sources = [target]
    for player in getattr(state, 'players', {}).values():
        sources.extend(state.cards[cid] for cid in player.battlefield if cid != card_id and state.cards[cid].zone == Zone.BATTLEFIELD)
    active, unsupported = [], []
    losses = None
    for source in sources:
        clauses = static_clauses(getattr(source, 'oracle_text', ''))
        if not any('attack' in clause or 'block' in clause for clause in clauses):
            continue
        # Prepare once for this read, never retain mutable state across decisions.
        if losses is None:
            losses = _printed_ability_loss_sources(state)
        if printed_abilities_suppressed(state, source.id, losses=losses):
            continue
        previous = None
        for clause in clauses:
            from rules_engine.combat_payments import parse_static_combat_tax
            tax = parse_static_combat_tax(clause, source.name)
            if tax:
                previous = _condition(state, source, target, tax['condition']) if tax['condition'] else None
                continue  # Dedicated declaration-payment reader; not a blanket attack ban.
            body, truth = clause, True
            if clause.startswith('otherwise, '):
                body = clause.removeprefix('otherwise, ')
                truth = None if previous is None else not previous
            else:
                previous = None
                body, condition, inverted = conditional_clause(clause)
                if condition is not None:
                    previous = _condition(state, source, target, condition)
                    truth = previous
                    if inverted:
                        truth = None if truth is None else not truth
            recipient = _recipient_body(state, source, target, body)
            if recipient is None or not BODY.match(recipient):
                continue
            record = {'source_id': source.id, 'source_name': source.name, 'clause': clause, 'body': recipient}
            if truth is None:
                unsupported.append({**record, 'reason': 'unresolved combat condition'})
            elif truth:
                # Payment and unparsed qualifiers must not become blanket restrictions.
                if re.search(r'\b(?:unless|as long as|if)\b', recipient) and not recipient.endswith('if able'):
                    unsupported.append({**record, 'reason': 'unresolved combat qualifier'})
                elif not supported_body(recipient):
                    unsupported.append({**record, 'reason': 'unimplemented combat clause'})
                else:
                    active.append(record)
    return {'active': active, 'unsupported': unsupported}


def combat_rule_text(state, card_id):
    return '\n'.join(record['body'] for record in combat_rule_view(state, card_id)['active'])
