"""Durable authorized card observations, distinct from current hidden state."""
from copy import deepcopy
from dataclasses import asdict

from game_state.state import CardInstance, Zone


def public_card_ids(state):
    visible = {cid for player in state.players.values()
               for cid in player.battlefield + player.graveyard}
    visible.update(item.source_card_id for item in state.stack)
    visible.update(cid for player in state.players.values() for cid in player.exile
                   if not state.cards[cid].exile_face_down)
    return visible


def observe_cards(state, card_ids, viewers=(1, 2)):
    """Call only at an actual public reveal/transition or owned inspection."""
    if getattr(state, 'ai_information_player', None) is not None:
        return  # Projected effects cannot manufacture new authoritative knowledge.
    for cid in card_ids:
        card = state.cards.get(cid)
        if card is None or not card.name or card.exile_face_down:
            continue
        record = asdict(card)
        record['zone'] = card.zone.value
        for pid in viewers:
            state.card_observations.setdefault(pid, {})[cid] = deepcopy(record)


def remembered_hand_card(state, player_id, card):
    """Identity survives an observed public return, never a hidden library trip.

    Library observations are deliberately not restored by physical ID: an unseen
    reorder would otherwise disclose the remembered card's actual new position.
    """
    if card.zone != Zone.HAND:
        return None
    record = getattr(state, 'card_observations', {}).get(player_id, {}).get(card.id)
    if not record:
        return None
    previous = Zone(record['zone'])
    delta = card.zone_change_sequence - record['zone_change_sequence']
    if not (previous == Zone.HAND and delta == 0
            or previous in {Zone.BATTLEFIELD, Zone.GRAVEYARD, Zone.STACK} and delta == 1):
        return None
    known = CardInstance(**{**deepcopy(record), 'zone': previous})
    if previous != Zone.HAND:
        known.move_to_zone(Zone.HAND)
        known.controller = known.owner
        known.tapped = False
        known.summoning_sick = False
    return known
