"""Explicit private library ordering and optional shuffle during resolution."""
import re

from game_state.state import Zone

REORDER = re.compile(
    r'look at the top (a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+) '
    r'cards? of your library, then put them back in any order\.'
    r'(?P<shuffle>\s*you may shuffle(?: your library)?\.)?'
    r'(?P<draw>\s*draw a card\.)?', re.I)


def reorder_clause(text):
    match = REORDER.fullmatch(text.strip())
    if not match:
        return None
    from rules_engine.oracle_effects import _parse_count_token
    return {'top_n': _parse_count_token(match[1]),
            'optional_shuffle': bool(match['shuffle']), 'draw_after': bool(match['draw'])}


def _shuffle_prompt(state, controller, inspected, previous=None):
    state.pending_mechanic_choice = {
        **(previous or {}), 'kind': 'library_shuffle', 'player_id': controller,
        'options': ['keep', 'shuffle'], 'count': 1, 'min_count': 1,
        'label': 'Keep this order or shuffle your library',
        'option_labels': {'keep': 'Keep order', 'shuffle': 'Shuffle'},
        'inspected_card_ids': list(inspected),
    }


def look_reorder(state, controller, payload):
    library = state.players[controller].library
    count = max(0, int(payload['top_n']))
    top = list(reversed(library[-count:])) if count else []
    if len(top) > 1:
        state.pending_mechanic_choice = {
            'kind': 'library_order_shuffle' if payload.get('optional_shuffle') else 'library_top_order',
            'player_id': controller, 'options': top, 'count': len(top), 'min_count': len(top),
            'inspected_card_ids': top, 'label': 'Order these cards, topmost first',
        }
    elif payload.get('optional_shuffle'):
        _shuffle_prompt(state, controller, top)
    if state.pending_mechanic_choice:
        state.priority_player = controller
        state.passed_priority = set()


def finish_reorder(state, player_id, action):
    pending = state.pending_mechanic_choice
    ids = action.get('card_ids')
    if (pending['player_id'] != player_id or not isinstance(ids, list)
            or any(not isinstance(cid, str) for cid in ids) or len(set(ids)) != len(ids)):
        return False
    library = state.players[player_id].library
    if pending['kind'] == 'library_shuffle':
        if len(ids) != 1 or ids[0] not in {'keep', 'shuffle'}:
            return False
        if ids[0] == 'shuffle':
            state.rng.shuffle(library)
            state.log.append(f'{state.players[player_id].name} shuffles their library.')
    else:
        options = pending['options']
        if (set(ids) != set(options) or len(ids) != len(options)
                or list(reversed(library[-len(options):])) != options
                or any(state.cards[cid].zone != Zone.LIBRARY for cid in options)):
            return False
        library[-len(ids):] = reversed(ids)
        if pending['kind'] == 'library_order_shuffle':
            _shuffle_prompt(state, player_id, ids, pending)
            return True
    state.pending_mechanic_choice = None
    from rules_engine.stack_engine import resume_paused_resolution
    resume_paused_resolution(state, pending)
    return True
