"""Complete self-granted activated instructions, retained on one physical object."""
from copy import deepcopy
from functools import lru_cache
import re

from game_state.state import Zone, allocate_effect_timestamp, object_incarnation
from rules_engine.action_validation import ActionRejected


def reference(card):
    return {'incarnation': object_incarnation(card), 'sequence': card.zone_change_sequence}


def instruction_candidate(text, source_name=''):
    subject = r'this (?:saga|permanent|creature|artifact|enchantment|land)'
    if source_name:
        subject += '|' + re.escape(source_name)
    return bool(re.match(r'(?:' + subject + r') gains\s+(?:[\"\u201c]|\{|\'(?=\{))', text.strip(), re.I))


@lru_cache(maxsize=4096)
def compile_instruction(text, source_name=''):
    if not instruction_candidate(text, source_name):
        return None
    subject = r'this (?:saga|permanent|creature|artifact|enchantment|land)'
    if source_name:
        subject += '|' + re.escape(source_name)
    match = re.fullmatch(r'(?:' + subject + r') gains ([\"\u201c])(.+)([\"\u201d])\.?',
                         text.strip(), re.I | re.S)
    if match is None or {'"': '"', '\u201c': '\u201d'}[match[1]] != match[3]:
        raise ActionRejected('Unsupported complete activated-ability grant')
    cost, colon, body = match[2].partition(':')
    cost, body = cost.strip(), body.strip()
    from rules_engine.costs import parse_activated_cost
    from rules_engine.mana import fixed_mana_vector, fixed_mana_alternatives
    from rules_engine.token_descriptors import complete_quoted_creature_token_body
    parsed = parse_activated_cost(cost)
    mana = fixed_mana_vector(body) is not None or fixed_mana_alternatives(body) is not None
    if (not colon or not parsed.supported or not body
            or not mana and complete_quoted_creature_token_body(body) is None):
        raise ActionRejected('Unsupported complete granted cost or instruction')
    return {'cost': cost, 'body': body, 'kind': 'mana' if mana else 'activated'}


def top_level_offsets(text):
    """Offsets preserve the legacy regex enumeration; quoted costs are not printed."""
    result, depth, quote, escaped = [], 0, None, False
    for char in text:
        result.append(depth == 0 and quote is None)
        if depth:
            depth += (char == '(') - (char == ')')
        elif quote is not None:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == quote:
                quote = None
        elif char == '(':
            depth = 1
        elif char == ')':
            return None
        elif char in ('"', '\u201c'):
            quote = '"' if char == '"' else '\u201d'
    return None if depth or quote is not None else result


def validate_records(card):
    records = getattr(card, 'activated_ability_effects', [])
    if type(records) is not list:
        raise ActionRejected('Invalid activated-ability effect list')
    seen = set()
    fields = {'cost', 'body', 'kind', 'ability_index', 'incarnation', 'sequence',
              'timestamp', 'source_card_id', 'source_name'}
    for record in records:
        if (type(record) is not dict or set(record) != fields
                or any(type(record[k]) is not int for k in
                       ('ability_index', 'incarnation', 'sequence', 'timestamp'))
                or not 0 <= record['ability_index'] <= 100 or record['ability_index'] in seen
                or record['timestamp'] <= 0
                or card.zone != Zone.BATTLEFIELD
                or reference(card) != {k: record[k] for k in ('incarnation', 'sequence')}
                or any(type(record[k]) is not str for k in ('cost', 'body', 'kind', 'source_card_id', 'source_name'))
                or record['kind'] not in {'mana', 'activated'}):
            raise ActionRejected('Invalid activated-ability effect record')
        instruction = compile_instruction('This permanent gains "' + record['cost'] + ': ' + record['body'] + '"')
        if instruction != {k: record[k] for k in ('cost', 'body', 'kind')}:
            raise ActionRejected('Activated-ability effect instruction changed')
        seen.add(record['ability_index'])
    return records


def _index_floor(card, state=None):
    from rules_engine.oracle_effects import ACTIVATED_ABILITY_RE
    from rules_engine.mana_abilities import _printed_mana_ability_specs
    rows = _printed_mana_ability_specs(card, state)
    return max(len(list(ACTIVATED_ABILITY_RE.finditer(card.oracle_text or ''))),
               max((r[0] + 1 for r in rows), default=0))


def records(card, state=None):
    retained = validate_records(card)
    if not retained:
        return []
    current = [r for r in retained if card.zone == Zone.BATTLEFIELD
               and reference(card) == {k: r[k] for k in ('incarnation', 'sequence')}]
    if state is not None:
        from rules_engine.continuous import effective_activated_grants
        current = list(effective_activated_grants(state, card.id))
    # Printed indices retain their native domain, including quoted regex holes.
    if any(r['ability_index'] < _index_floor(card, state) for r in current):
        raise ActionRejected('Printed and granted ability index domains overlap')
    return [dict(record) for record in current]


def resolve_grant(state, controller, payload):
    card = state.cards.get(payload.get('target_card_id'))
    retained = payload.get('reference')
    if (type(retained) is not dict or set(retained) != {'incarnation', 'sequence'}
            or any(type(value) is not int or value < 0 for value in retained.values())):
        raise ActionRejected('Invalid granted-ability recipient reference')
    if (card is None or card.zone != Zone.BATTLEFIELD or reference(card) != payload.get('reference')
            or not any(card.id in player.battlefield for player in state.players.values())):
        return
    instruction = compile_instruction('This permanent gains "' + payload['cost'] + ': ' + payload['body'] + '"')
    if instruction != {k: payload[k] for k in ('cost', 'body', 'kind')}:
        raise ActionRejected('Changed granted instruction')
    previous = validate_records(card)
    floor = _index_floor(card, state)
    used = {r['ability_index'] for r in previous}
    index = next((n for n in range(100, floor-1, -1) if n not in used), None)
    if index is None:
        raise ActionRejected('No stable public activated-ability index remains')
    card.activated_ability_effects.append({**deepcopy(instruction), **reference(card),
        'ability_index': index, 'timestamp': allocate_effect_timestamp(state),
        'source_card_id': card.id, 'source_name': card.name})


def ordinary_specs(card, state=None):
    return [{'index': r['ability_index'], 'mana_cost': r['cost'], 'text': r['body'],
             'raw_body': r['body'], 'raw_effect_text': r['body'], 'activation_zone': 'battlefield',
             'cost_modifier': None, 'label': r['cost'] + ': ' + r['body'],
             '__granted_ability': r['ability_index']}
            for r in records(card, state) if r['kind'] == 'activated']


def mana_specs(card, state=None):
    return [(r['ability_index'], r['cost'], r['body'])
            for r in records(card, state) if r['kind'] == 'mana']
