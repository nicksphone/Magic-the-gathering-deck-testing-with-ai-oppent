"""Single mana kicker and supported spell-conditional instruction surfaces."""
import re
from copy import copy

from rules_engine.oracle_text import without_reminder_text

PRICE = re.compile(r'^kicker ((?:\{(?:\d+|[WUBRGCS]|[2WUBRGC]/[WUBRGC]|[WUBRG]/P)\})+)\s*$', re.I | re.M)
CONDITION = re.compile(r'\bif this spell was kicked, ([^.]+)\.', re.I)


def permanent_kicker(text):
    """Recognize self-entry counters or a fixed conditional self-ETB payoff."""
    from rules_engine.spell_cost_clauses import COUNT, NUMBERS
    text = without_reminder_text(text or '').strip()
    prices = list(PRICE.finditer(text))
    if len(prices) != 1 or re.search(r'\bmultikicker\b', text, re.I):
        return None
    remaining = PRICE.sub('', text).strip()
    counter = re.fullmatch(r'If this creature was kicked, it enters with ' + COUNT +
                           r' (\+1/\+1|-1/-1) counters? on it\.', remaining, re.I)
    if counter:
        amount = int(counter[1]) if counter[1].isdigit() else NUMBERS[counter[1].lower()]
        return {'price': prices[0][1], 'counters': {counter[2]: amount}}
    trigger = re.fullmatch(r'(When this (?:creature|artifact|enchantment|permanent) enters(?: the battlefield)?,) '
                           r'if it was kicked, (.+\.)', remaining, re.I)
    if not trigger:
        return None
    instruction = trigger[2]
    if not re.fullmatch(r'(?:draw ' + COUNT + r' cards?|it deals \d+ damage to target creature|'
                        r'destroy target noncreature permanent)\.', instruction, re.I):
        return None
    return {'price': prices[0][1], 'instruction': instruction,
            'clause': trigger[1] + ' ' + instruction}


def kicker_price(card):
    if set(getattr(card, 'types', []) or []).intersection({'Instant', 'Sorcery'}):
        parsed = kicker_surfaces(card.oracle_text)
        return parsed[0] if parsed else None
    parsed = permanent_kicker(card.oracle_text)
    return parsed['price'] if parsed else None


def kicker_surfaces(text):
    """Return price/base/kicked text, or None when semantics remain unmodeled."""
    text = without_reminder_text(text or '').strip()
    prices = list(PRICE.finditer(text))
    if len(prices) != 1 or re.search(r'\bmultikicker\b', text, re.I):
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
        else:
            return None
        kicked = prefix + suffix
    return prices[0][1], base, kicked.strip()


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
