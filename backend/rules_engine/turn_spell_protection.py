"""Complete color-conditioned draw and temporary spell/player protection."""
import re

from game_state.state import Zone
from rules_engine.colors import card_color_symbols
from rules_engine.keyword_effects import add_keyword_effect
from rules_engine.oracle_text import without_reminder_text


COLORS = {'white': 'W', 'blue': 'U', 'black': 'B', 'red': 'R', 'green': 'G'}
COLOR = '(?:white|blue|black|red|green)'
INSTRUCTION = re.compile(
    rf'Draw a card if an opponent has cast a (?P<draw>{COLOR}(?: or {COLOR})*) spell this turn\.\s*'
    r"Spells you control can't be countered this turn\.\s*"
    rf'You and permanents you control gain hexproof from (?P<shield>{COLOR}(?: and from {COLOR})*) '
    r'until end of turn\.', re.I)
CANDIDATE = re.compile(r'^Draw a card if an opponent has cast a\b', re.I)


def compile_instruction(text):
    body = without_reminder_text(text or '').strip()
    if not CANDIDATE.match(body):
        return None
    match = INSTRUCTION.fullmatch(body)
    if match is None:
        return 'noop', {'__unsupported_instruction': 'unsupported complete color-conditioned protection'}
    draw = [COLORS[color.lower()] for color in re.findall(COLOR, match['draw'], re.I)]
    shield = [color.lower() for color in re.findall(COLOR, match['shield'], re.I)]
    return 'effect_sequence', {'effects': [
        {'effect_key': 'conditional_color_draw', 'payload': {'colors': draw}},
        {'effect_key': 'grant_turn_spell_protection', 'payload': {'colors': shield}},
    ]}


def record_spell_colors(state, source, controller):
    state.spell_color_history[controller].update(card_color_symbols(source, state) if source else ())


def conditional_draw(state, controller, payload):
    colors = set(payload['colors'])
    qualifies = any(colors & seen for player, seen in state.spell_color_history.items()
                    if player != controller)
    if not qualifies and not state.spell_color_history_known:
        from rules_engine.action_validation import ActionRejected
        raise ActionRejected('Legacy snapshot does not retain spell-cast color history')
    if qualifies:
        from effects.registry import resolve_effect
        resolve_effect(state, controller, 'draw_cards', {**payload, 'amount': 1})


def grant_protection(state, controller, payload):
    colors = set(payload['colors'])
    if not colors or not colors <= COLORS.keys():
        raise ValueError('Invalid turn protection colors')
    state.turn_spell_protection.add(controller)
    state.turn_player_hexproof.setdefault(controller, set()).update(colors)
    for cid in list(state.players[controller].battlefield):
        card = state.cards.get(cid)
        if card and card.zone == Zone.BATTLEFIELD and card.controller == controller:
            add_keyword_effect(state, cid, sorted('hexproof from ' + color for color in colors),
                               until_end_of_turn=True, source_card_id=payload.get('__source_card_id'))


def restore_history(state, payload):
    """Reject malformed new protocol fields; do not invent old color history."""
    def color_map(key, allowed, default):
        raw = payload.get(key, default)
        if not isinstance(raw, dict) or set(raw) - {'1', '2'}:
            raise ValueError('Invalid ' + key)
        result = {}
        for player, values in raw.items():
            if (not isinstance(values, list) or any(not isinstance(v, str) for v in values)
                    or len(values) != len(set(values)) or not set(values) <= allowed):
                raise ValueError('Invalid ' + key)
            result[int(player)] = set(values)
        return result

    state.spell_color_history = color_map('spell_color_history', set(COLORS.values()), {'1': [], '2': []})
    if set(state.spell_color_history) != {1, 2}:
        raise ValueError('Incomplete spell color history')
    known = payload.get('spell_color_history_known',
                        'spell_color_history' in payload or not any(state.spells_cast_this_turn.values()))
    if type(known) is not bool:
        raise ValueError('Invalid spell color history status')
    state.spell_color_history_known = known
    state.turn_player_hexproof = color_map('turn_player_hexproof', set(COLORS), {})
    players = payload.get('turn_spell_protection', [])
    if (not isinstance(players, list) or any(type(p) is not int or p not in {1, 2} for p in players)
            or len(players) != len(set(players))):
        raise ValueError('Invalid spell protection players')
    state.turn_spell_protection = set(players)
