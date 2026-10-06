"""Bounded optional resolution costs, not optional free effect inference."""
from copy import copy
from contextlib import contextmanager
from contextvars import ContextVar
import re


PAYMENT = re.compile(r'you may pay ((?:\{(?:\d{1,6}|[wubrgcs])\})+)\. if you do, (.+)', re.I)
TOKEN = re.compile(
    r'create (?:a|an|\d+) \d+/\d+ '
    r'(?:(?:white|blue|black|red|green|colorless)(?: and)? )+'
    r'[a-z]+ creature tokens?(?: with flying)?\.', re.I)
DRAIN = re.compile(r'each opponent loses (\d+) life and you gain (\d+) life\.', re.I)
DRAW = re.compile(r'draw (?:a|one|\d+) cards?\.', re.I)
RESOLUTION_PAYER = ContextVar('resolution_mana_payer', default=None)


@contextmanager
def resolution_mana_payment(player):
    token = RESOLUTION_PAYER.set(player)
    try:
        yield
    finally:
        RESOLUTION_PAYER.reset(token)


def resolution_mana_ability_allowed(state, card, spec):
    payer = RESOLUTION_PAYER.get()
    if payer is None or spec is None:
        return True
    if card.controller != payer:
        return False
    # The payment window grants mana activation, not priority. Unknown printed
    # activation restrictions stay unavailable, independently for each ability.
    text = spec[2].lower()
    restriction = re.search(r'\bactivate\b[^.]*\bonly\b[^.]*', text)
    if not restriction:
        return True
    return (restriction[0] == 'activate only during your turn'
            and state.active_player == payer)


def compile_paid_instruction(state, source, controller, instruction, event_payload):
    """Compile only complete supported bodies from the caller's matched clause."""
    if len(instruction) > 8192:
        return None
    match = PAYMENT.fullmatch(instruction.strip())
    if match is None:
        return None
    cost, body = match.groups()
    drain = DRAIN.fullmatch(body)
    if drain:
        key, data = 'effect_sequence', {'effects': [
            {'effect_key': 'lose_life', 'payload': {'target_player': pid, 'amount': int(drain[1])}}
            for pid in sorted(state.players) if pid != controller
        ] + [{'effect_key': 'gain_life', 'payload': {'target_player': controller, 'amount': int(drain[2])}}]}
    elif TOKEN.fullmatch(body) or DRAW.fullmatch(body):
        from rules_engine.oracle_effects import infer_effect_from_oracle
        # Instruction-only compiler view; never change the actual source's facts.
        proxy = copy(source)
        proxy.oracle_text, proxy.card_faces, proxy.types = body, [], []
        proxy.selected_face_index = None
        key, data = infer_effect_from_oracle(state, proxy, controller,
            {**event_payload, 'source_card_id': source.id}, report_unsupported=False)
        if key != ('create_token' if TOKEN.fullmatch(body) else 'draw_cards'):
            return None
        data['keywords'] = [keyword.title() for keyword in data.get('keywords', [])]
    else:
        return None
    return key, {**data, '__may': True, '__optional_payment_cost': cost.upper(),
                 '__optional_payment_instruction': instruction}


def can_pay_optional(state, item):
    from rules_engine.mana import can_pay_with_pool_and_lands
    with resolution_mana_payment(item.controller):
        return can_pay_with_pool_and_lands(state, item.controller,
            item.payload['__optional_payment_cost'], payment_kind='resolution', apply_modifiers=False)


def pay_optional(state, item):
    from rules_engine.mana import auto_pay_cost
    if item.payload.get('__optional_payment_paid'):
        return True
    details = {}
    with resolution_mana_payment(item.controller):
        if not auto_pay_cost(state, item.controller, item.payload['__optional_payment_cost'],
                             payment_kind='resolution', apply_modifiers=False, payment_details=details):
            return False
    item.payload['__optional_payment_paid'] = details
    return True
