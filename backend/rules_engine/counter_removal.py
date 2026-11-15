"""Gameplay counter removal is distinct from counters ceasing on zone changes."""
from game_state.state import Zone, object_incarnation
from rules_engine.type_effects import effective_types


def _storage(card, kind):
    if kind == 'loyalty' and (card.loyalty is not None or 'Planeswalker' in effective_types(None, card)):
        return None
    return '__lore' if kind == 'lore' and 'Saga' in card.type_line else kind


def counter_count(state, card, kind):
    if kind == 'loyalty' and (card.loyalty is not None or 'Planeswalker' in effective_types(state, card)):
        return max(0, int(card.loyalty or 0))
    return max(0, int(card.counters.get(_storage(card, kind), 0)))


def remove_counters(state, card_id, kind, amount, *, emit_events=True):
    """Return actual counters removed; never consume internal damage/buff markers."""
    card = state.cards.get(card_id)
    if (card is None or card.zone != Zone.BATTLEFIELD or type(kind) is not str
            or kind.startswith('__')):
        return 0
    before = counter_count(state, card, kind)
    removed = min(before, max(0, int(amount)))
    if not removed:
        return 0
    after = before-removed
    key = _storage(card, kind)
    if key is None:
        card.loyalty = after
    elif after:
        card.counters[key] = after
    else:
        card.counters.pop(key, None)
    if not after:
        card.counter_timestamps.pop(kind, None)
        if key is not None:
            card.counter_timestamps.pop(key, None)
    if emit_events and kind == 'defense':
        from rules_engine.events import emit_event
        emit_event(state, 'defense_counters_removed', {
            'card_id': card.id, 'controller': card.controller,
            'old_defense': before, 'new_defense': after, 'amount': removed,
            'source_reference': {'incarnation': object_incarnation(card),
                                 'zone_change_sequence': card.zone_change_sequence}})
    return removed


def resolve_remove(state, controller, payload):
    del controller
    card = state.cards.get(payload.get('target_card_id'))
    if card is None:
        return
    kind = payload.get('counter', 'defense')
    amount = counter_count(state, card, kind) if payload.get('all') else payload.get('amount', 1)
    remove_counters(state, card.id, kind, amount)


def resolve_move(state, controller, payload):
    """Prepare placement choices before committing either half of a counter move."""
    from rules_engine.action_validation import ActionRejected
    from rules_engine.counter_placement import counter_placement_forbidden, put_counters
    from rules_engine.counter_replacements import counter_effect_amount
    source = state.cards.get(payload.get('from_card_id'))
    target = state.cards.get(payload.get('target_card_id'))
    proof = payload.get('__counter_move')
    kind = payload.get('counter', 'defense')
    valid = (source is not None and target is not None and source is not target
             and source.zone == target.zone == Zone.BATTLEFIELD
             and type(kind) is str and not kind.startswith('__'))
    if not valid:
        if proof is not None:
            raise ActionRejected('Stale counter move source or recipient')
        return
    count = counter_count(state, source, kind)
    if proof is None:
        amount = min(count, max(0, int(payload.get('amount', 1))))
    else:
        if type(proof) is not dict or type(proof.get('removed_amount')) is not int:
            raise ActionRejected('Invalid retained counter move')
        amount = proof['removed_amount']
    expected = {'version': 1, 'from_card_id': source.id, 'target_card_id': target.id,
        'controller': controller, 'counter': kind, 'removed_amount': amount, 'source_count': count,
        'source_reference': {'incarnation': object_incarnation(source), 'zone_change_sequence': source.zone_change_sequence},
        'target_reference': {'incarnation': object_incarnation(target), 'zone_change_sequence': target.zone_change_sequence},
        'target_controller': target.controller, 'target_count': counter_count(state, target, kind)}
    if proof is not None and (proof != expected or type(proof.get('version')) is not int
            or any(type(proof.get(key)) is not int for key in ('controller','source_count','target_controller','target_count'))
            or any(type(value) is not int for key in ('source_reference','target_reference') for value in proof[key].values())):
        raise ActionRejected('Stale retained counter move')
    if amount <= 0 or amount > count:
        return
    # CR122.5: neither half happens when removal or placement is impossible.
    if counter_placement_forbidden(state, kind, target_card_id=target.id):
        return
    event = {**payload, 'counter': kind, '__counter_move': expected}
    if proof is None:
        event['amount'] = amount
    placed = counter_effect_amount(state, controller, 'move_counters', event)
    if placed is None:
        return
    remove_counters(state, source.id, kind, amount)
    put_counters(state, kind, placed, target_card_id=target.id, placement_checked=True)
