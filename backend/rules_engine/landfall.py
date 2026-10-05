"""Complete, alternative landfall instructions; no partial clause guessing."""
import re

from rules_engine.land_history import landfall_status


CONDITION = r'\s*Landfall\s*[\u2014-]\s*If you had a land enter the battlefield under your control this turn, '
COUNT = r'(a|one|two|three|four|five|six|seven|eight|nine|ten|\d+)'
PATTERNS = [
    re.compile(r'Target creature gets ([+-]\d+)/([+-]\d+) until end of turn\.' + CONDITION
               + r'that creature gets ([+-]\d+)/([+-]\d+) until end of turn instead\.', re.I),
    re.compile(r'Target player gains (\d+) life\.' + CONDITION
               + r'that player gains (\d+) life instead\.', re.I),
    re.compile(r'Draw ' + COUNT + r' cards?\.' + CONDITION + r'draw ' + COUNT + r' cards? instead\.', re.I),
]


def alternative_effect(oracle, targets):
    for index, pattern in enumerate(PATTERNS):
        match = pattern.fullmatch(oracle.strip())
        if match is None:
            continue
        if index == 0:
            values = [int(value) for value in match.groups()]
            branches = [{'effect_key': 'temporary_pt_buff', 'payload': {
                'target_card_id': targets.get('target_card_id'), 'power': values[offset],
                'toughness': values[offset+1]}} for offset in [0, 2]]
        elif index == 1:
            branches = [{'effect_key': 'gain_life', 'payload': {
                'target_player': targets.get('target_player'), 'amount': int(value)}}
                for value in match.groups()]
        else:
            from rules_engine.oracle_effects import _parse_count_token
            counts = [_parse_count_token(value.lower()) for value in match.groups()]
            if any(count <= 0 for count in counts):
                return None
            branches = [{'effect_key': 'draw_cards', 'payload': {'amount': count}} for count in counts]
        return 'landfall_alternative', {'branches': branches}
    return None


def require_known_history(state, controller):
    if landfall_status(state, controller) is None:
        from rules_engine.action_validation import ActionRejected
        raise ActionRejected('Cannot resolve landfall with unknown legacy land-entry history')


def resolve_alternative(state, controller, payload):
    from effects.registry import resolve_effect
    require_known_history(state, controller)
    branch = payload['branches'][int(landfall_status(state, controller))]
    data = {**branch['payload'], **{key: value for key, value in payload.items() if key.startswith('__')}}
    resolve_effect(state, controller, branch['effect_key'], data)
