"""Public entry events, independent of land plays and surviving permanents."""
from game_state.state import Zone
from rules_engine.type_effects import effective_types


def record_land_entry(state, payload):
    if state.pregame_pending:
        return
    card = state.cards.get(payload.get('card_id'))
    if (card is None or card.zone != Zone.BATTLEFIELD or card.controller not in state.players
            or 'Land' not in effective_types(state, card)):
        return
    state.land_entries_this_turn[card.controller] = state.land_entries_this_turn.get(card.controller, 0) + 1


def landfall_status(state, controller):
    """None means a legacy snapshot cannot establish absence of an entry."""
    if state.land_entries_this_turn.get(controller, 0) > 0:
        return True
    return False if state.land_entry_history_known else None
