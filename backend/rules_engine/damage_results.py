from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar

from rules_engine.continuous import has_keyword
from rules_engine.replacement import player_cant_lose_life


_damage_counters = ContextVar('damage_counters', default=None)


HAND_CONTEXT_KEYS = ('__activation_source_context', '__activation_source_origin',
                     '__activation_source_reference', '__ability_target_text')


def validate_hand_source_context(state, context, *, source_card_id, source_reference, ability_text):
    """Validate retained native provenance, not arbitrary storage authenticity."""
    from rules_engine.action_validation import ActionRejected
    from rules_engine.card_types import CARD_TYPES
    from rules_engine.costs import parse_activated_cost
    def require(condition):
        if not condition:
            raise ActionRejected('Malformed retained HAND source context')
    require(type(context) is dict and set(context) == {
        'version', 'source_card_id', 'origin_zone', 'source_reference', 'owner',
        'controller', 'colors', 'types', 'keyword_counts', 'ability'})
    require(type(context['version']) is int and context['version'] == 1)
    require(type(context['source_card_id']) is str and bool(context['source_card_id'])
            and context['source_card_id'] == source_card_id and context['origin_zone'] == 'hand')
    reference = context['source_reference']
    require(type(reference) is dict and set(reference) == {'incarnation', 'zone_change_sequence'}
            and all(type(value) is int and value >= 0 for value in reference.values())
            and type(source_reference) is dict and reference == source_reference
            and all(type(value) is int for value in source_reference.values()))
    require(type(context['owner']) is int and context['owner'] in state.players
            and context['controller'] is None)
    colors, types = context['colors'], context['types']
    require(type(colors) is list and all(type(value) is str and value in 'WUBRG' and len(value) == 1 for value in colors)
            and colors == sorted(set(colors)))
    require(type(types) is list and bool(types) and all(type(value) is str and value in CARD_TYPES for value in types)
            and types == sorted(set(types)))
    counts = context['keyword_counts']
    require(type(counts) is dict and all(type(key) is str and bool(key) and key == key.lower()
            and type(value) is int and value > 0 for key, value in counts.items()))
    ability = context['ability']
    require(type(ability) is dict and set(ability) == {'index', 'cost', 'text'})
    require(type(ability['index']) is int and ability['index'] >= 0
            and type(ability['cost']) is str and bool(ability['cost'])
            and type(ability['text']) is str and bool(ability['text']) and ability['text'] == ability_text)
    cost = parse_activated_cost(ability['cost'])
    require(cost.supported and cost.discard_source)
    return context


def capture_hand_source_context(state, source_card_id, *, player_id, ability):
    from game_state.state import Zone, object_incarnation
    from rules_engine.action_validation import ActionRejected
    from rules_engine.colors import card_color_symbols
    from rules_engine.continuous import effective_keyword_counts
    from rules_engine.type_effects import effective_types
    card = state.cards[source_card_id]
    if (card.zone != Zone.HAND or card.owner != player_id or source_card_id not in state.players[player_id].hand
            or ability['activation_zone'] != 'hand'):
        raise ActionRejected('HAND context requires genuine pre-cost hand source')
    context = {'version': 1, 'source_card_id': source_card_id, 'origin_zone': 'hand',
        'source_reference': {'incarnation': object_incarnation(card), 'zone_change_sequence': card.zone_change_sequence},
        'owner': card.owner, 'controller': None, 'colors': sorted(card_color_symbols(card, state)),
        'types': sorted(set(effective_types(state, card))),
        'keyword_counts': {key: value for key, value in effective_keyword_counts(state, source_card_id).items() if value > 0},
        'ability': {'index': ability['index'], 'cost': ability['mana_cost'], 'text': ability['text']}}
    return validate_hand_source_context(state, context, source_card_id=source_card_id,
        source_reference=context['source_reference'], ability_text=ability['text'])


def validate_hand_payload(state, payload, *, source_card_id=None, parent=None):
    """Preflight all inherited sequence contexts before any sibling can mutate."""
    from rules_engine.action_validation import ActionRejected
    root = payload if parent is None else parent
    context = root.get('__activation_source_context')
    if '__activation_source_context' not in root:
        if root.get('__activation_source_origin') == 'hand':
            raise ActionRejected('Native HAND activation requires retained context')
        context = None
    else:
        source_card_id = source_card_id or root.get('__source_card_id')
        validate_hand_source_context(state, context, source_card_id=source_card_id,
            source_reference=root.get('__activation_source_reference'), ability_text=root.get('__ability_target_text'))
        if (root.get('__activation_source_origin') != 'hand' or root.get('__trigger_event')
                or root.get('__stack_copy_kind') in ('spell', 'triggered')):
            raise ActionRejected('Conflicting HAND activation origin')
        if any(context['keyword_counts'].get(key, 0) for key in ('infect', 'wither')):
            raise ActionRejected('HAND counter damage placer is outside the supported boundary')
    pending = [payload]
    while pending:
        data = pending.pop()
        if not isinstance(data, dict):
            if context is not None:
                raise ActionRejected('Malformed HAND instruction payload')
            continue
        if context is not None:
            validate_hand_source_context(state, data.get('__activation_source_context', context),
                source_card_id=source_card_id,
                source_reference=data.get('__activation_source_reference', root.get('__activation_source_reference')),
                ability_text=data.get('__ability_target_text', root.get('__ability_target_text')))
            if (any(key in data and data[key] != root.get(key) for key in HAND_CONTEXT_KEYS)
                    or data.get('__source_lki') is not None
                    or data.get('__source_card_id', source_card_id) != source_card_id):
                raise ActionRejected('Conflicting retained HAND instruction context')
        elif data is not root and ('__activation_source_context' in data or data.get('__activation_source_origin') == 'hand'):
            if source_card_id is not None:
                raise ActionRejected('Unbound child HAND activation context')
            validate_hand_payload(state, data, source_card_id=data.get('__source_card_id'))
            continue
        if 'effects' in data:
            effects = data['effects']
            if context is not None and (type(effects) is not list or any(type(effect) is not dict for effect in effects)):
                raise ActionRejected('Malformed retained HAND sequence')
            if isinstance(effects, list):
                pending.extend(effect.get('payload', {}) for effect in effects if isinstance(effect, dict))
        if context is not None and 'recipients' in data:
            recipients = data['recipients']
            if type(recipients) is not list or any(type(recipient) is not dict for recipient in recipients):
                raise ActionRejected('Malformed retained HAND damage recipients')
            pending.extend(recipients)
    return context


def damage_source_control(state, source_id, *, source_lki=None, source_context=None, source_controller=None):
    if source_context is not None:
        from rules_engine.action_validation import ActionRejected
        if type(source_context) is not dict or type(source_context.get('ability')) is not dict:
            raise ActionRejected('Malformed retained HAND source context')
        validate_hand_source_context(state, source_context, source_card_id=source_id,
            source_reference=source_context.get('source_reference'), ability_text=source_context.get('ability', {}).get('text'))
        if source_lki is not None or source_controller is not None:
            from rules_engine.action_validation import ActionRejected
            raise ActionRejected('Conflicting HAND source control provenance')
        return None
    return source_controller if source_controller in state.players else damage_controller(state, source_id, source_lki)


def validate_hand_damage_continuation(state, pending):
    """Bind private choice data to the actual retained resolving item before clear."""
    from rules_engine.action_validation import ActionRejected
    frame = pending.get('resolving_item') or {}
    if type(frame) is not dict:
        raise ActionRejected('Malformed retained damage continuation frame')
    parent = frame.get('payload') or {}
    retained = pending.get('source_payload') or {}
    if type(parent) is not dict or type(retained) is not dict:
        raise ActionRejected('Malformed retained damage continuation payload')
    if ('__activation_source_context' not in parent and '__activation_source_context' not in retained
            and '__activation_source_context' not in pending):
        return retained
    if type(frame) is not dict or frame.get('source_card_id') != pending.get('source_card_id'):
        raise ActionRejected('HAND damage continuation requires actual retained frame')
    context = validate_hand_payload(state, parent, source_card_id=frame['source_card_id'])
    if context is None or any(retained.get(key) != parent.get(key) for key in HAND_CONTEXT_KEYS):
        raise ActionRejected('Conflicting retained HAND damage continuation')
    validate_hand_payload(state, {**retained, '__source_card_id': pending.get('source_card_id'),
                                 '__source_lki': pending.get('source_lki')})
    for effect in pending.get('continuation_effects', []):
        validate_hand_payload(state, effect.get('payload', {}), source_card_id=frame['source_card_id'], parent=parent)
    return retained


def damage_lifelink_beneficiary(state, source_id, *, source_lki=None, source_context=None):
    if source_context is not None:
        damage_source_control(state, source_id, source_lki=source_lki, source_context=source_context)
        return source_context['owner']
    return damage_controller(state, source_id, source_lki)


@contextmanager
def collect_damage_counters(state):
    """Collect simultaneous results without leaking into another match or AI copy."""
    packets = []
    token = _damage_counters.set((state, packets))
    try:
        yield packets
    finally:
        _damage_counters.reset(token)


def flush_damage_counters(state, packets):
    grouped = {}
    for event in packets:
        payload = event['payload']
        key = (event['controller'], event['effect_key'], payload.get('target_player'),
               payload.get('target_card_id'), payload['counter'],
               payload.get('__counter_is_effect', False))
        if key not in grouped:
            grouped[key] = {**event, 'payload': dict(payload)}
        else:
            grouped[key]['payload']['amount'] += payload['amount']
            if grouped[key]['payload'].get('__counter_reason') != payload.get('__counter_reason'):
                grouped[key]['payload']['__counter_reason'] = 'infect/toxic'
    for event in grouped.values():
        queue_damage_counters(state, event['controller'], event['effect_key'], event['payload'])


def source_has_keyword(state, source_id: str | None, keyword: str, source_lki: dict | None = None, *, source_context=None) -> bool:
    if source_context is not None:
        damage_source_control(state, source_id, source_lki=source_lki, source_context=source_context)
        return source_context['keyword_counts'].get(keyword, 0) > 0
    if source_lki is not None:
        return keyword in {str(value).lower() for value in source_lki.get("keywords", [])}
    return source_id in state.cards and has_keyword(state, source_id, keyword)


def damage_controller(state, source_id, source_lki=None, fallback=None, *, source_context=None):
    if source_context is not None:
        return damage_source_control(state, source_id, source_lki=source_lki, source_context=source_context)
    if source_lki and source_lki.get('controller') in state.players:
        return source_lki['controller']
    if source_id in state.cards:
        return state.cards[source_id].controller
    return fallback if fallback in state.players else state.active_player


def queue_damage_counters(state, controller, effect_key, payload):
    """Keep damage results inside one deferred-SBA event, preserving each placer."""
    from effects.registry import resolve_effect
    collector = _damage_counters.get()
    if collector is not None and collector[0] is state:
        collector[1].append({'controller': controller, 'effect_key': effect_key, 'payload': payload})
        return
    pending = state.pending_replacement_choice or state.pending_mechanic_choice
    if pending:
        pending.setdefault('counter_continuation_queue', []).append(
            {'controller': controller, 'effect_key': effect_key, 'payload': payload})
    else:
        resolve_effect(state, controller, effect_key, payload)


def apply_player_damage(state, player_id: int, amount: int, source_id: str | None, *, combat: bool = False,
                        source_lki: dict | None = None, controller=None, counter_is_effect=False, source_context=None) -> None:
    """Apply consequences of damage after replacements and prevention."""
    if amount <= 0:
        return
    player = state.players[player_id]
    placer = damage_controller(state, source_id, source_lki, controller, source_context=source_context)
    infect = source_has_keyword(state, source_id, "infect", source_lki, source_context=source_context)
    poison = amount if infect else 0
    reason = 'infect' if infect else 'toxic'
    if not infect and not player_cant_lose_life(state, player_id):
        player.life -= amount
    if combat and source_id in state.cards:
        toxic = sum(int(value) for value in re.findall(r"\btoxic\s+(\d+)", state.cards[source_id].oracle_text, re.IGNORECASE))
        if toxic:
            poison += toxic
            if infect:
                reason = 'infect/toxic'
    if poison:
        queue_damage_counters(state, placer, 'add_player_counters', {
            'target_player': player_id, 'counter': 'poison', 'amount': poison,
            '__counter_is_effect': counter_is_effect, '__counter_reason': reason})


def apply_creature_damage(state, card_id: str, amount: int, source_id: str | None,
                          *, source_lki: dict | None = None, controller=None, counter_is_effect=False, source_context=None) -> None:
    if amount <= 0:
        return
    card = state.cards[card_id]
    if source_has_keyword(state, source_id, 'deathtouch', source_lki, source_context=source_context):
        card.counters['__deathtouch_damaged'] = 1
    counter_damage = any(source_has_keyword(state, source_id, keyword, source_lki, source_context=source_context) for keyword in ("infect", "wither"))
    if counter_damage:
        queue_damage_counters(state, damage_controller(state, source_id, source_lki, controller),
                              'add_counters', {'target_card_id': card_id, 'counter': '-1/-1',
                                               'amount': amount, '__counter_is_effect': counter_is_effect})
    else:
        card.counters['__damage_marked'] = int(card.counters.get('__damage_marked', 0)) + amount
