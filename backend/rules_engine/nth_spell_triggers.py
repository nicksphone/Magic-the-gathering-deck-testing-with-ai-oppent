"""Bounded full-clause nth-cast triggers; recognition is not card certification."""
from copy import copy
import re

ORDINALS = {'first':1, 'second':2, 'third':3, 'fourth':4, 'fifth':5, 'sixth':6,
            'seventh':7, 'eighth':8, 'ninth':9, 'tenth':10}
CLAUSE = re.compile(
    r'^(?:[a-z][a-z -]*\s*[\u2014\u2013-]\s*)?whenever you cast your '
    r'(' + '|'.join(ORDINALS) + r'|\d+(?:st|nd|rd|th)) spell '
    r"(each turn|in a turn|during each opponent's turn), (.+)$", re.I)
COUNT = r'(?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)'
DRAW = re.compile(r'draw ' + COUNT + r' cards?\.', re.I)
TOKEN = re.compile(
    r'create ' + COUNT + r' \d+/\d+ [a-z -]+ creature tokens?'
    r'(?: with (?P<keyword>flying|vigilance|haste|defender|lifelink|reach|menace|trample|deathtouch))?\.', re.I)
DRAW_TOKEN = re.compile(r'(draw ' + COUNT + r' cards?), then (create .+)', re.I)


def _instruction(state, card, text):
    from rules_engine.oracle_effects import infer_effect_from_oracle
    sequence = DRAW_TOKEN.fullmatch(text)
    if sequence:
        first = _instruction(state, card, sequence[1] + '.')
        second = _instruction(state, card, sequence[2])
        if first and second:
            return 'effect_sequence', {'effects': [
                {'effect_key':first[0], 'payload':first[1]},
                {'effect_key':second[0], 'payload':second[1]},
            ]}
        return None
    if not (DRAW.fullmatch(text) or TOKEN.fullmatch(text)):
        return None
    proxy = copy(card)
    proxy.oracle_text, proxy.card_faces, proxy.types = text, [], []
    proxy.selected_face_index = None
    key, data = infer_effect_from_oracle(state, proxy, card.controller, report_unsupported=False)
    if key == 'draw_cards' and DRAW.fullmatch(text):
        return key, data
    if key == 'create_token' and TOKEN.fullmatch(text):
        # Require a printed descriptor, never the legacy parser's token defaults.
        from rules_engine.token_descriptors import creature_token_descriptor
        descriptor = creature_token_descriptor(text)
        if descriptor and descriptor['name'] != 'Token' and not data.get('__unsupported_token_quantity'):
            keyword = TOKEN.fullmatch(text)['keyword']
            data['keywords'] = [keyword.lower()] if keyword else []
            return key, data
    return None


def collect_nth_spell_triggers(state, card, event, payload, oracle):
    triggers, remaining = [], []
    for line in oracle.splitlines():
        match = CLAUSE.fullmatch(line.strip())
        if not match:
            remaining.append(line)
            continue
        # Remove this complete clause from legacy substring dispatch, including copies.
        if event != 'spell_cast' or payload.get('controller') != card.controller:
            continue
        ordinal = match[1].lower()
        number = ORDINALS.get(ordinal)
        if number is None:
            number = int(re.match(r'\d+', ordinal)[0])
        if state.spells_cast_this_turn.get(card.controller, 0) != number:
            continue
        if match[2].lower() == "during each opponent's turn" and state.active_player == card.controller:
            continue
        effect = _instruction(state, card, match[3])
        if effect is None:
            state.log.append(f'Unsupported nth-spell trigger instruction for {card.name}: {line.strip()}')
            continue
        key, data = effect
        triggers.append({'source_card_id':card.id, 'controller':card.controller,
                         'label':f'{card.name} nth-spell trigger', 'effect_key':key,
                         'payload':{**data, '__trigger_full_clause':line.strip(),
                                    '__nth_spell_count':number, '__nth_spell_turn':state.turn}})
    return triggers, '\n'.join(remaining)
