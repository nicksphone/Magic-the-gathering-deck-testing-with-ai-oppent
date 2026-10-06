"""Explicit library shuffle actions, not a wrapper around randomization."""
from game_state.state import StackItem, object_incarnation


def shuffle_library(state, player_id, *, resolving_item=None):
    from rules_engine.events import emit_event
    from rules_engine.targeting import stack_object_kind

    if type(player_id) is not int or player_id not in state.players:
        raise ValueError('Unknown shuffling player')
    cause = None
    if resolving_item is not None:
        item = StackItem(**resolving_item)
        source = state.cards.get(item.source_card_id)
        if source is None or type(item.controller) is not int or item.controller not in state.players:
            raise ValueError('Shuffle requires a retained resolving source and controller')
        cause = {
            'stack_id': item.id, 'source_card_id': item.source_card_id,
            'controller': item.controller, 'kind': stack_object_kind(state, item),
            'source_reference': {'incarnation': object_incarnation(source),
                                 'zone_change_sequence': source.zone_change_sequence},
        }
    state.rng.shuffle(state.players[player_id].library)
    state.log.append(f'{state.players[player_id].name} shuffles their library.')
    emit_event(state, 'shuffle', {'player_id': player_id, 'cause': cause})
