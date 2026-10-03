"""Object-bound type additions, with a materialized view for current type readers."""
from game_state.state import Zone, allocate_effect_timestamp, object_incarnation


def active_type_effects(card):
    return [effect for effect in card.type_effects
            if card.zone == Zone.BATTLEFIELD and effect['incarnation'] == object_incarnation(card)]


def copiable_types(card):
    if card.type_effect_base is not None:
        return list(card.type_effect_base)
    return [kind for kind in card.types if not card.counters.get('__crew_added_' + kind.lower())]


def refresh_type_effects(card):
    if card.type_effect_base is None:
        return
    base = list(card.type_effect_base)
    effects = sorted(active_type_effects(card), key=lambda effect: effect['timestamp'])
    card.types = list(dict.fromkeys([*base, *(kind for effect in effects for kind in effect['types'])]))
    if not card.type_effects:
        card.type_effect_base = None


def add_type_effect(state, card_id, types, *, until_end_of_turn=False, timestamp=None, source_card_id=None):
    card = state.cards.get(card_id)
    if card is None or card.zone != Zone.BATTLEFIELD or not types:
        return
    if card.type_effect_base is None and '__crew_until_turn' in card.counters:
        card.type_effect_base = copiable_types(card)
        card.type_effects.append({
            'types': ['Artifact', 'Creature'], 'until_end_of_turn': True,
            'timestamp': int(card.effect_timestamp or card.static_order or 0),
            'incarnation': object_incarnation(card), 'timestamp_origin': 'legacy_inferred',
            'source_card_id': card.id, 'source_name': card.name,
        })
        for flag in ('__crew_until_turn', '__crew_added_artifact', '__crew_added_creature'):
            card.counters.pop(flag, None)
    if card.type_effect_base is None:
        card.type_effect_base = list(card.types)
    source = state.cards.get(source_card_id)
    card.type_effects.append({
        'types': list(dict.fromkeys(types)), 'until_end_of_turn': until_end_of_turn,
        'timestamp': allocate_effect_timestamp(state) if timestamp is None else timestamp,
        'incarnation': object_incarnation(card), 'timestamp_origin': 'resolution',
        'source_card_id': source_card_id, 'source_name': source.name if source else None,
    })
    refresh_type_effects(card)


def clear_type_effects(card):
    if card.type_effect_base is not None:
        card.types = list(card.type_effect_base)
    else:
        # Old crew snapshots record exactly which types the effect contributed.
        for kind in ('Creature', 'Artifact'):
            if card.counters.get('__crew_added_' + kind.lower()) and kind in card.types:
                card.types.remove(kind)
    card.type_effects.clear()
    card.type_effect_base = None


def rebase_type_effects(card):
    """A face/copy change replaces layer-one types, not later animation effects."""
    if card.type_effect_base is not None:
        card.type_effect_base = list(card.types)
        refresh_type_effects(card)
