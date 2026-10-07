"""Single fixed kicker cost and supported conditional instruction surfaces."""
import re
from copy import copy

from rules_engine.oracle_text import without_reminder_text

PRICE = re.compile(r'^kicker(?: ((?:\{(?:\d+|[WUBRGCS]|[2WUBRGC]/[WUBRGC]|[WUBRG]/P)\})+)|[\u2014-]\s*([^\n.]+)\.?)\s*$', re.I | re.M)
CONDITION = re.compile(r'\bif this spell was kicked, ([^.]+)\.', re.I)

TOKEN_INSTRUCTION = r'create (?:a|an|one|two|three|four|five|\d+) \d+/\d+ (?:white|blue|black|red|green|colorless) [a-z-]+ creature tokens?(?: with flying)?\.'


def validate_kicker_count(count, kicked):
    """Explicit payment counts are distinct from absent legacy metadata."""
    if type(count) is not int or count not in (0, 1, 2) or type(kicked) is not bool or kicked != (count > 0):
        raise ValueError('Invalid explicit kicker count or kicked flag')
    return count


def paired_permanent_kicker(card):
    """Compile the complete two-price, independent self-entry damage body."""
    if not set(getattr(card, 'types', []) or []).intersection({'Creature'}):
        return None
    lines = [line.strip() for line in without_reminder_text(card.oracle_text or '').splitlines()
             if line.strip()]
    price = re.fullmatch(r'kicker ((?:\{[WUBRGC]\})+) and/or ((?:\{[WUBRGC]\})+)',
                        lines[0], re.I) if lines else None
    if not price:
        return None
    remaining = lines[1:]
    if remaining and re.fullmatch(r'(?:flying|lifelink)(?:, (?:flying|lifelink))*', remaining[0], re.I):
        remaining = remaining[1:]
    if len(remaining) != 2:
        return None
    triggers = []
    reference = r'(?:this creature|' + re.escape(card.name) + r')'
    for threshold, line in enumerate(remaining, 1):
        match = re.fullmatch(r'when ' + reference + r' enters(?: the battlefield)?, if it was kicked'
                             + (r' twice' if threshold == 2 else '')
                             + r', (it deals ([1-9]\d*) damage to any target\.)', line, re.I)
        if not match:
            return None
        triggers.append({'threshold': threshold, 'clause': line, 'instruction': match[1]})
    return {'prices': (price[1].upper(), price[2].upper()), 'triggers': triggers}


def kicker_components(price):
    if price.startswith('{'):
        return {'mana_cost': price}
    from rules_engine.spell_cost_clauses import fixed_cost_component
    parsed = fixed_cost_component(price)
    return {'mana_cost': '', **parsed} if parsed else None


def _fixed_price(text):
    prices = list(PRICE.finditer(text))
    if len(prices) != 1 or re.search(r'\bmultikicker\b', text, re.I):
        return None
    price = prices[0][1] or prices[0][2]
    return price if kicker_components(price) else None


def kicked_cast_clauses(text):
    """Only fixed self-counter, temporary base-stat and creature-token payoffs."""
    from rules_engine.spell_cost_clauses import COUNT
    clauses = []
    for line in without_reminder_text(text or '').splitlines():
        match = re.fullmatch(r'whenever you cast a kicked spell, (.+\.)', line.strip(), re.I)
        if match and re.fullmatch(
            r'(?:this creature has base power and toughness \d+/\d+ until end of turn\.|'
            r'put ' + COUNT + r' \+1/\+1 counters? on this creature\.|' +
            TOKEN_INSTRUCTION + r')', match[1], re.I):
            clauses.append({'clause': line.strip(), 'instruction': match[1]})
    return clauses


def permanent_kicker(text):
    """Recognize self-entry counters or a fixed conditional self-ETB payoff."""
    from rules_engine.spell_cost_clauses import COUNT, NUMBERS
    text = without_reminder_text(text or '').strip()
    price = _fixed_price(text)
    if price is None:
        return None
    remaining = PRICE.sub('', text).strip()
    cast_clauses = {entry['clause'] for entry in kicked_cast_clauses(remaining)}
    remaining = '\n'.join(line for line in remaining.splitlines() if line.strip() not in cast_clauses)
    counter = re.fullmatch(r'If this creature was kicked, it enters with ' + COUNT +
                           r' (\+1/\+1|-1/-1) counters? on it\.', remaining, re.I)
    if counter:
        amount = int(counter[1]) if counter[1].isdigit() else NUMBERS[counter[1].lower()]
        return {'price': price, 'counters': {counter[2]: amount}}
    trigger = re.fullmatch(r'(When this (?:creature|artifact|enchantment|permanent) enters(?: the battlefield)?,) '
                           r'if it was kicked, (.+\.)', remaining, re.I)
    if not trigger:
        return None
    instruction = trigger[2]
    if not re.fullmatch(r'(?:draw ' + COUNT + r' cards?|it deals \d+ damage to target creature|'
                        r'destroy target noncreature permanent)\.|' + TOKEN_INSTRUCTION, instruction, re.I):
        return None
    return {'price': price, 'instruction': instruction,
            'clause': trigger[1] + ' ' + instruction}


def kicker_price(card):
    if set(getattr(card, 'types', []) or []).intersection({'Instant', 'Sorcery'}):
        parsed = kicker_surfaces(card.oracle_text)
        return parsed[0] if parsed else None
    parsed = permanent_kicker(card.oracle_text)
    return parsed['price'] if parsed else None


def kicker_cost(card):
    price = kicker_price(card)
    return kicker_components(price) if price is not None else None


def kicker_surfaces(text):
    """Return price/base/kicked text, or None when semantics remain unmodeled."""
    text = without_reminder_text(text or '').strip()
    price = _fixed_price(text)
    if price is None:
        return None
    text = PRICE.sub('', text).strip()
    matches = list(CONDITION.finditer(text))
    if not matches or len(matches) != len(re.findall(r'\bkicked\b', text, re.I)):
        return None
    base = CONDITION.sub('', text).strip()
    kicked = text
    for match in reversed(matches):
        prefix, suffix = kicked[:match.start()], kicked[match.end():]
        instruction = match[1].strip()
        if not instruction.lower().endswith(' instead'):
            count = r'(?:a|one|two|three|four|five|six|seven|eight|nine|ten|\d+)'
            if not re.fullmatch(r'(?:draw ' + count + r' cards?|gain \d+ life|(?:scry|surveil) \d+)', instruction, re.I):
                return None
            kicked = prefix + instruction + '.' + suffix
            continue
        instruction = instruction[:-8]
        damage = re.fullmatch(r'it deals (\d+) damage( divided as you choose among any number of targets)?', instruction, re.I)
        pump = re.fullmatch(r'that creature gets ([+-]\d+/[+-]\d+) until end of turn', instruction, re.I)
        discard = re.fullmatch(r'that player discards (a|one|two|three|four|five|six|seven|eight|nine|ten|\d+) cards?', instruction, re.I)
        if damage:
            previous = list(re.finditer(r'([^.!\n]*?\bdeals? )\d+ damage([^.]*?)\.', prefix, re.I))
            if not previous:
                return None
            last = previous[-1]
            tail = damage[2] or last[2]
            prefix = prefix[:last.start()] + last[1] + damage[1] + ' damage' + tail + '.' + prefix[last.end():]
        elif pump:
            previous = list(re.finditer(r'\bgets [+-]\d+/[+-]\d+ until end of turn', prefix, re.I))
            if not previous:
                return None
            last = previous[-1]
            prefix = prefix[:last.start()] + 'gets ' + pump[1] + ' until end of turn' + prefix[last.end():]
        elif discard:
            previous = list(re.finditer(r'target player discards (a|one|two|three|four|five|six|seven|eight|nine|ten|\d+) cards?\.', prefix, re.I))
            if not previous:
                return None
            last = previous[-1]
            prefix = prefix[:last.start()] + 'Target player discards ' + discard[1] + ' cards.' + prefix[last.end():]
        else:
            return None
        kicked = prefix + suffix
    return price, base, kicked.strip()


def spell_kicker_view(card, kicked=False):
    """Do not mutate printed text, faces, or a permanent's later abilities."""
    if not set(getattr(card, 'types', []) or []).intersection({'Instant', 'Sorcery'}):
        return card
    parsed = kicker_surfaces(card.oracle_text)
    if not parsed:
        return card
    view = copy(card)
    view.oracle_text = parsed[2 if kicked else 1]
    view.card_faces = []
    return view
