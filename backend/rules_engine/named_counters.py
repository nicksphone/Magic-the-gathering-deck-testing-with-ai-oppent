"""Rules-defined counter abilities and untap replacement, independent of names."""
from game_state.state import Zone
from contextlib import contextmanager
from contextvars import ContextVar


_shield_damage_event = ContextVar('shield_damage_event', default=None)


@contextmanager
def shield_damage_event(state):
    """One simultaneous combat event; never shared with another match/AI copy."""
    token = _shield_damage_event.set((state, set()))
    try:
        yield
    finally:
        _shield_damage_event.reset(token)


def shield_applied_in_event(state, card_id):
    event = _shield_damage_event.get()
    return bool(event is not None and event[0] is state and card_id in event[1])


def apply_shield_damage(state, card_id):
    if shield_applied_in_event(state, card_id):
        return
    if remove_shield_counter(state, card_id):
        event = _shield_damage_event.get()
        if event is not None and event[0] is state:
            event[1].add(card_id)


KEYWORD_COUNTERS = frozenset({
    'flying', 'first strike', 'double strike', 'deathtouch', 'decayed', 'exalted',
    'haste', 'hexproof', 'indestructible', 'lifelink', 'menace', 'reach', 'shadow',
    'trample', 'vigilance',
})


def keyword_counter(kind):
    kind = str(kind).strip().lower()
    if kind in KEYWORD_COUNTERS:
        return kind
    if kind.startswith('hexproof from ') or kind == 'trample over planeswalkers':
        return kind
    return None


def remove_shield_counter(state, card_id):
    """One rules-defined effect per permanent, not one per counter."""
    card = state.cards.get(card_id)
    if card is None or card.zone != Zone.BATTLEFIELD or card.counters.get('shield', 0) <= 0:
        return False
    card.counters['shield'] -= 1
    if not card.counters['shield']:
        card.counters.pop('shield')
        card.counter_timestamps.pop('shield', None)
    state.log.append(f'{card.name} removes a shield counter.')
    return True


def destruction_prevented(state, card_id):
    """Effect-driven destruction only; never use for sacrifice or an SBA."""
    from rules_engine.continuous import has_keyword
    if has_keyword(state, card_id, 'indestructible'):
        state.log.append(f'{state.cards[card_id].name} cannot be destroyed because it has indestructible.')
        return True
    return remove_shield_counter(state, card_id)


def untap_permanent(state, card_id, *, turn_based=False):
    card = state.cards.get(card_id)
    if card is None or card.zone != Zone.BATTLEFIELD or not card.tapped:
        return False
    if turn_based:
        import re
        from rules_engine.continuous import _static_oracle_text
        text = _static_oracle_text(card)
        subject = rf'(?:this (?:creature|permanent|artifact|land)|{re.escape(card.name.lower())})'
        if re.search(subject + r" (?:doesn't|does not) untap during your untap step", text):
            return False
    if int(card.counters.get('stun', 0)) > 0:
        card.counters['stun'] -= 1
        if not card.counters['stun']:
            card.counters.pop('stun')
            card.counter_timestamps.pop('stun', None)
        state.log.append(f'{card.name} removes a stun counter instead of untapping.')
        return False
    card.tapped = False
    return True
