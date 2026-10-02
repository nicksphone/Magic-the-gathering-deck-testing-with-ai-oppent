"""Pure, condition-aware supported static combat clauses and their provenance."""
import re
from functools import lru_cache

from game_state.state import Zone
from rules_engine.oracle_text import without_reminder_text

NUMBERS = {word: value for value, word in enumerate(('zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'))}
BODY = re.compile(r"^(?:(?:can't|cannot) (?:attack|block|be blocked)|can block|attacks each combat|blocks each combat|must (?:attack|block))\b")


def supported_body(text):
    return bool(re.fullmatch(
        r"(?:(?:can't|cannot) (?:attack(?: or block)?|block)(?: alone| artifact creatures)?"
        r"|(?:can't|cannot) be blocked(?: by creatures with power \d+ or (?:less|greater)"
        r"| except by (?:\d+|one|two|three|four|five|six|seven|eight|nine|ten) or more creatures)?"
        r"|can block (?:any number of creatures|an additional creature each combat"
        r"|(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten) additional creatures each combat"
        r"|only creatures with flying)"
        r"|(?:attacks|blocks) each combat if able|must (?:attack|block) each combat if able)", text))


def number(token):
    return int(token) if token.isdigit() else NUMBERS.get(token)


@lru_cache(maxsize=4096)
def static_clauses(oracle):
    lines = []
    for line in without_reminder_text(oracle or '').lower().splitlines():
        line = line.strip()
        if re.match(r'^(?:when|whenever|at the beginning|during)\b', line) or ':' in line or 'until end of turn' in line:
            continue
        line = re.sub(r'"[^"]*"|\u201c[^\u201d]*\u201d', '""', line)
        lines.extend(part.strip(' .') for part in re.split(r'\.\s+', line) if part.strip(' .'))
    return tuple(lines)


def _land_count(state, player_ids, subtype=None):
    return sum(
        card.zone == Zone.BATTLEFIELD and 'Land' in card.types
        and (subtype is None or subtype in re.split(r'\s+', (card.type_line or '').lower().split('—')[-1]))
        for pid in player_ids for cid in state.players[pid].battlefield
        for card in [state.cards[cid]]
    )


def _condition(state, source, target, text):
    from rules_engine.continuous import _attached_condition
    land = re.fullmatch(r'you control (\w+) or more lands', text)
    if land and number(land[1]) is not None:
        return _land_count(state, [source.controller]) >= number(land[1])
    defender_land = re.fullmatch(r'defending player controls an? (island|forest|swamp|mountain|plains)', text)
    if defender_land:
        return _land_count(state, [3-target.controller], defender_land[1]) > 0
    global_land = re.fullmatch(r'there are (\w+) or more (islands|forests|swamps|mountains|plains) on the battlefield', text)
    if global_land and number(global_land[1]) is not None:
        subtype = global_land[2] if global_land[2] == 'plains' else global_land[2].removesuffix('s')
        return _land_count(state, list(state.players), subtype) >= number(global_land[1])
    counters = re.fullmatch(r'(?:it|this creature) has (\w+) or more ([+\-]\d+/[+\-]\d+) counters on it', text)
    if counters and number(counters[1]) is not None:
        return target.counters.get(counters[2], 0) >= number(counters[1])
    return _attached_condition(state, source, target, text)


def _recipient_body(state, source, target, text):
    self_subject = rf'(?:this (?:creature|permanent)|cardname|{re.escape(source.name.lower())}) '
    if source.id == target.id:
        match = re.match(self_subject, text)
        if match:
            return text[match.end():]
        if BODY.match(text):
            return text
    if getattr(source, 'attached_to', None) == target.id and 'Creature' not in source.types:
        match = re.match(r'(?:enchanted|equipped|fortified) (?:creature|permanent) |it ', text)
        if match:
            return text[match.end():]
    if re.match(r'(?:this|it|enchanted|equipped|fortified)\b', text):
        return None
    global_subject = re.fullmatch(r'(other )?(?:each )?([a-z -]+?) (you control|your opponents control)?\s*('
                                  r"(?:(?:can't|cannot) (?:attack|block|be blocked)|can block|attacks each combat|blocks each combat|must (?:attack|block))\b.*)", text)
    if global_subject and BODY.match(global_subject[4]):
        from rules_engine.continuous import _scope_controller, _subject_matches
        scope = global_subject[3]
        if (not global_subject[1] or source.id != target.id) and (scope is None or _scope_controller(source.controller, scope, target.controller)):
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
            body, truth = clause, True
            if clause.startswith('otherwise, '):
                body = clause.removeprefix('otherwise, ')
                truth = None if previous is None else not previous
            else:
                previous = None
                prefix = re.fullmatch(r'(?:as long as|if) (.+?), (.+)', clause)
                suffix = re.fullmatch(r'(.+?) (as long as|unless) (.+)', clause)
                if prefix or suffix:
                    condition = prefix[1] if prefix else suffix[3]
                    body = prefix[2] if prefix else suffix[1]
                    previous = _condition(state, source, target, condition)
                    truth = previous
                    if suffix and suffix[2] == 'unless':
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
