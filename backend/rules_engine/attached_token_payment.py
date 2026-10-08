"""Complete attached-creature payment/copy instructions with mandatory fallback."""
import re
from copy import deepcopy

from game_state.state import Zone, object_incarnation
from rules_engine.oracle_text import without_reminder_text


KEY = 'attached_token_payment'
CLAUSE = re.compile(
    r'(?:Landfall\s*[\u2014\u2013-]\s*)?Whenever a land '
    r'(?:you control enters|enters the battlefield under your control), '
    r'you may pay (?P<cost>(?:\{(?:\d{1,6}|[WUBRGC])\})+) if this permanent '
    r'is attached to a creature you control\. If you do, create a token '
    r"that's a copy of that creature\. If you didn't create a token this way, "
    r'create a (?P<power>\d{1,3})/(?P<toughness>\d{1,3}) '
    r'(?P<color>white|blue|black|red|green|colorless) '
    r'(?P<subtype>[a-z]+) creature token\.', re.I)
COLORS = dict(white='W', blue='U', black='B', red='R', green='G', colorless='')


def reference(card):
    return [object_incarnation(card), card.zone_change_sequence]


def current(state, cid, ref):
    card = state.cards.get(cid)
    return (card is not None and card.zone == Zone.BATTLEFIELD
            and type(ref) is list and len(ref) == 2
            and all(type(value) is int and value >= 0 for value in ref)
            and reference(card) == ref and card.controller in state.players
            and cid in state.players[card.controller].battlefield)


def copiable_lki(state, card):
    from effects.handlers import token_copy_descriptor
    from rules_engine.type_effects import effective_types
    data = token_copy_descriptor(card)
    data['loyalty'] = card.loyalty
    if card.layout in {'transform', 'modal_dfc', 'double_faced_token'}:
        from rules_engine.action_validation import ActionRejected
        face = card.selected_face_index if card.selected_face_index is not None else 0
        if len(card.card_faces) != 2 or type(face) is not int or face not in (0, 1):
            raise ActionRejected('Malformed copiable double-faced permanent')
        data.update(card_faces=deepcopy(card.card_faces), layout='double_faced_token',
                    selected_face_index=face)
    return {'reference': reference(card), 'controller': card.controller,
            'types': list(effective_types(state, card)), 'descriptor': deepcopy(data)}


def attachment_lki(state, card):
    host = state.cards.get(card.attached_to)
    return {'source_reference': reference(card), 'host_id': card.attached_to,
            'host': copiable_lki(state, host) if host is not None else None}


def retain_departed_host(state, card, snapshot):
    for item in state.stack:
        if item.effect_key != KEY:
            continue
        source = state.cards.get(item.source_card_id)
        if current(state, item.source_card_id, item.payload.get('__attached_source_reference')):
            info = attachment_lki(state, source)
        else:
            info = (item.payload.get('__source_lki') or {}).get('__attachment_lki') or {}
        if (info.get('host_id') == card.id
                and (info.get('host') or {}).get('reference') == snapshot['reference']):
            item.payload['__attached_host_lki'] = deepcopy(snapshot)


def compile_instruction(source, oracle):
    text = without_reminder_text(oracle or '')
    candidates = [line.strip() for line in text.splitlines()
                  if re.search(r'you may pay .+ if this permanent is attached', line, re.I)]
    if not candidates:
        return None
    if len(candidates) != 1 or len(candidates[0]) > 8192:
        return 'noop', {'__unsupported_trigger_instruction': oracle}
    match = CLAUSE.fullmatch(candidates[0])
    if match is None:
        return 'noop', {'__unsupported_trigger_instruction': candidates[0]}
    color = COLORS[match['color'].lower()]
    subtype = match['subtype'].capitalize()
    return KEY, {'__trigger_full_clause': candidates[0],
                 '__attached_source_reference': reference(source),
                 '__attached_payment_cost': match['cost'].upper(),
                 '__attached_fallback': {'name': subtype, 'types': ['Creature', 'Token'],
                     'type_line': 'Token Creature - ' + subtype,
                     'power': int(match['power']), 'toughness': int(match['toughness']),
                     'colors': [color] if color else []}}


def attached_host(state, source_id, payload, controller):
    source = state.cards.get(source_id)
    if current(state, source_id, payload.get('__attached_source_reference')):
        info = attachment_lki(state, source)
    else:
        info = (payload.get('__source_lki') or {}).get('__attachment_lki') or {}
        if info.get('source_reference') != payload.get('__attached_source_reference'):
            return None
    host_id = info.get('host_id')
    host = info.get('host')
    if host is None:
        return None
    if current(state, host_id, host['reference']):
        host = copiable_lki(state, state.cards[host_id])
    elif current(state, source_id, payload.get('__attached_source_reference')):
        return None
    else:
        departed = payload.get('__attached_host_lki')
        if departed is not None and departed.get('reference') == host['reference']:
            host = departed
    return {'id': host_id, **host} if host['controller'] == controller and 'Creature' in host['types'] else None


def prepare(state, item):
    """Only the nested payment is optional; decline retains the fallback body."""
    payload = item.payload
    if payload.get('__attached_payment_prepared'):
        if payload.get('__may_decided') and not payload.get('__may_choose'):
            payload['__attached_branch'] = 'fallback'
            payload['__may'] = False
            payload.pop('__optional_payment_cost', None)
        return
    host = attached_host(state, item.source_card_id, payload, item.controller)
    payload['__attached_payment_prepared'] = True
    payload['__attached_branch'] = 'copy' if host is not None else 'fallback'
    if host is not None:
        payload['__attached_host_id'] = host['id']
        payload['__attached_selected_host'] = host
        payload['__optional_payment_cost'] = payload['__attached_payment_cost']
        payload['__may'] = True
        payload['__may_choose'] = True
    else:
        payload['__may'] = False
        payload.pop('__optional_payment_cost', None)


def resolve(state, controller, payload):
    from effects.handlers import create_token
    if payload.get('__attached_branch') == 'copy' and payload.get('__optional_payment_paid'):
        selected = payload['__attached_selected_host']
        cid = selected['id']
        if current(state, cid, selected['reference']):
            selected = copiable_lki(state, state.cards[cid])
        elif cid in state.cards:
            departed = state.cards[cid].last_known_battlefield.get('__copiable_lki')
            if departed is not None and departed.get('reference') == selected['reference']:
                selected = departed
        before = set(state.cards)
        create_token(state, controller, deepcopy(selected['descriptor']))
        if set(state.cards) != before or state.pending_mechanic_choice or state.pending_replacement_choice:
            return
    create_token(state, controller, dict(payload['__attached_fallback']))
