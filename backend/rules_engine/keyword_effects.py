"""Object-bound layer-six effects created by resolution, not physical counters."""
from game_state.state import Zone, allocate_effect_timestamp, object_incarnation


def add_keyword_effect(state, card_id, keywords, *, operation='grant', until_end_of_turn=False, timestamp=None, source_card_id=None):
    card = state.cards.get(card_id)
    if card is None or card.zone != Zone.BATTLEFIELD or not keywords:
        return
    stamp = allocate_effect_timestamp(state) if timestamp is None else timestamp
    source = state.cards.get(source_card_id)
    for keyword in keywords:
        card.keyword_effects.append({
            'keyword': keyword.lower(), 'operation': operation, 'timestamp': stamp,
            'until_end_of_turn': until_end_of_turn, 'incarnation': object_incarnation(card),
            'timestamp_origin': 'resolution',
            'source_card_id': source_card_id, 'source_name': source.name if source else None,
        })


def active_keyword_effects(card):
    return [effect for effect in getattr(card,'keyword_effects',[]) or []
            if effect['incarnation'] == object_incarnation(card)]


def restore_keyword_effects(raw):
    """Old snapshots never recorded grant timing; expose that inferred fallback."""
    from copy import deepcopy
    if 'keyword_effects' in raw:
        return deepcopy(raw['keyword_effects'])
    stamp = int(raw.get('effect_timestamp') or raw.get('static_order') or 0)
    incarnation = int(raw.get('battlefield_incarnation') if raw.get('battlefield_incarnation') is not None else stamp)
    return [{'keyword': keyword.lower(), 'operation': 'grant', 'timestamp': stamp,
             'until_end_of_turn': False, 'incarnation': incarnation, 'timestamp_origin': 'legacy_inferred'}
            for keyword in raw.get('granted_keywords', [])]
