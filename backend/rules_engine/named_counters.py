"""Rules-defined counter abilities and untap replacement, independent of names."""
from game_state.state import Zone


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
