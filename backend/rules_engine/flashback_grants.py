"""Object-bound, until-end-of-turn flashback at the printed mana cost."""
import re

from game_state.state import Zone, object_incarnation
from rules_engine.oracle_text import without_reminder_text


def grant_instruction(text):
    return bool(re.fullmatch(
        r'target instant or sorcery card in your graveyard gains flashback until end of turn\.\s*'
        r'the flashback cost is equal to its mana cost\.',
        without_reminder_text(text).lower().strip()))


def remember_target(state, item):
    if item.effect_key != 'grant_flashback':
        return
    target = state.cards.get(item.payload.get('target_card_id'))
    if target is not None:
        item.payload['__graveyard_reference'] = {
            'incarnation': object_incarnation(target), 'zone_sequence': target.zone_change_sequence}


def granted_cost(state, card, player_id):
    grant = getattr(card, 'granted_flashback', {})
    if (card.zone == Zone.GRAVEYARD and card.owner == player_id
            and grant.get('turn') == state.turn
            and grant.get('zone_sequence') == card.zone_change_sequence):
        return card.mana_cost or None
    return None


def resolve_grant(state, controller, payload):
    from rules_engine.type_effects import effective_types
    target = state.cards.get(payload.get('target_card_id'))
    reference = payload.get('__graveyard_reference') or {}
    if (target is None or target.zone != Zone.GRAVEYARD or target.owner != controller
            or target.id not in state.players[controller].graveyard
            or not {'Instant', 'Sorcery'}.intersection(effective_types(state, target))
            or reference.get('incarnation') != object_incarnation(target)
            or reference.get('zone_sequence') != target.zone_change_sequence):
        return
    target.granted_flashback = {'turn': state.turn, 'zone_sequence': target.zone_change_sequence}
    state.log.append(f'{target.name} gains flashback until end of turn at its mana cost.')
