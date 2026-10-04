"""Live devotion resources and exact supported payoff instructions."""
import re
from functools import lru_cache

from game_state.state import Zone
from rules_engine.oracle_text import without_reminder_text

COLORS = {'white': 'W', 'blue': 'U', 'black': 'B', 'red': 'R', 'green': 'G'}


@lru_cache(maxsize=4096)
def devotion_mana_instruction(text):
    text = without_reminder_text(text).strip().lower().rstrip('.')
    if text == 'choose a color. add an amount of mana of that color equal to your devotion to that color':
        return {'choice': True}
    match = re.fullmatch(r'add an amount of \{([wubrgc])\} equal to your devotion to ([a-z]+(?: and [a-z]+)?)', text)
    if match and all(color in COLORS for color in match[2].split(' and ')):
        return {'output_color': match[1].upper(), 'colors': tuple(COLORS[color] for color in match[2].split(' and '))}
    return None


def devotion_count(state, player_id, colors):
    """Each matching mana symbol contributes once, including hybrid symbols."""
    wanted = set(colors).intersection(COLORS.values())
    return sum(bool(wanted.intersection(symbol.upper().split('/')))
               for card in state.cards.values()
               if card.zone == Zone.BATTLEFIELD and card.controller == player_id
               for symbol in re.findall(r'\{([^{}]+)\}', card.mana_cost or ''))


def devotion_instruction(text, name=''):
    spec = _devotion_instruction(text, name)
    return {**spec, 'colors': list(spec['colors'])} if spec is not None else None


@lru_cache(maxsize=4096)
def _devotion_instruction(text, name):
    text = without_reminder_text(text).strip().lower().rstrip('.')
    colors = r'([a-z]+(?: and [a-z]+)?)'
    subject = r'(?:it|this creature' + ('|' + re.escape(name.lower()) if name else '') + ')'
    patterns = {
        'pump': r'target creature gets \+x/\+x until end of turn, where x is your devotion to ' + colors,
        'gain': r'you gain life equal to your devotion to ' + colors,
        'drain': r'each opponent loses x life, where x is your devotion to ' + colors
                 + r'\. you gain life equal to the life lost this way',
        'damage': subject + r' deals damage to each opponent equal to your devotion to ' + colors,
        'counters': r'put a number of \+1/\+1 counters on ' + subject + r' equal to your devotion to ' + colors,
        'tokens': r'create a number of (\d+/\d+ [a-z -]+ creature tokens(?: with [a-z ,]+)?)'
                  + r' equal to your devotion to ' + colors,
    }
    for kind, pattern in patterns.items():
        match = re.fullmatch(pattern, text)
        if match and all(color in COLORS for color in match[match.lastindex].split(' and ')):
            if kind == 'tokens' and ' with ' in match[1]:
                from rules_engine.continuous import _attached_keywords
                if _attached_keywords(match[1].split(' with ', 1)[1]) is None:
                    return None
            return {'kind': kind, 'colors': [COLORS[color] for color in match[match.lastindex].split(' and ')],
                    **({'token_text': match[1]} if kind == 'tokens' else {})}
    return None


def resolve_devotion_effect(state, controller, payload):
    from effects.registry import resolve_effect
    from effects.handlers import lose_life
    from rules_engine.oracle_effects import infer_effect_from_oracle
    from copy import copy
    spec = payload['devotion']
    amount = devotion_count(state, controller, spec['colors'])
    kind = spec['kind']
    if kind == 'pump':
        resolve_effect(state, controller, 'temporary_pt_buff', {
            **payload, 'power': amount, 'toughness': amount})
    elif kind == 'gain':
        resolve_effect(state, controller, 'gain_life', {**payload, 'amount': amount})
    elif kind == 'damage':
        resolve_effect(state, controller, 'effect_sequence', {**payload, 'effects': [
            {'effect_key': 'deal_damage', 'payload': {'target_player': pid, 'amount': amount}}
            for pid in state.players if pid != controller]})
    elif kind == 'drain':
        lost = 0
        for pid, player in state.players.items():
            if pid != controller:
                before = player.life
                lose_life(state, controller, {'target_player': pid, 'amount': amount})
                lost += before - player.life
        resolve_effect(state, controller, 'gain_life', {**payload, 'amount': lost})
    elif kind == 'counters':
        resolve_effect(state, controller, 'add_counters', {
            **payload, 'target_card_id': payload.get('__source_card_id'),
            'effect_timestamp': payload['source_incarnation'], 'amount': amount, 'counter': '+1/+1'})
    elif kind == 'tokens' and amount:
        source = state.cards.get(payload.get('__source_card_id'))
        if source is None:
            state.log.append('Devotion token effect has no retained source object.')
            return
        surface = copy(source)
        surface.types = []
        surface.card_faces = []
        surface.oracle_text = f"Create {amount} {spec['token_text']}."
        key, data = infer_effect_from_oracle(state, surface, controller, report_unsupported=False)
        assert key == 'create_token', 'Supported devotion token template must compile'
        resolve_effect(state, controller, key, {**payload, **data})
