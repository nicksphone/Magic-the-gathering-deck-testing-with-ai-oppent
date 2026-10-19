"""Closed self-entry modal instructions; explicit public selection before targets."""
from copy import deepcopy
import re



def compile_instruction(text):
    match = re.fullmatch(r'When this (?:creature|permanent) enters(?: the battlefield)?, choose one [\u2014-]\n(.+)', text.strip(), re.S)
    if not match:
        return None
    modes = []
    for line in match[1].splitlines():
        bullet = re.fullmatch(r'\u2022 (.+)', line)
        if not bullet:
            return None
        clause = bullet[1]
        creature = re.fullmatch(r"Remove all counters from target creature\. It can't have counters put on it for as long as this (?:creature|permanent) remains on the battlefield\.", clause)
        player = re.fullmatch(r"Target opponent loses all counters\. That player can't get counters for as long as this (?:creature|permanent) remains on the battlefield\.", clause)
        if not creature and not player:
            return None
        modes.append({'label': clause, 'target_kind': 'card' if creature else 'player'})
    return modes if 2 <= len(modes) <= 8 else None


def selected(item, mode):
    chosen = deepcopy(item)
    chosen.payload.pop('__modal_modes', None)
    chosen.effect_key = 'retained_counter_prohibition'
    chosen.payload['__counter_target_kind'] = mode['target_kind']
    chosen.payload['__counter_mode_clause'] = mode['label']
    return chosen


def begin(state, item, continuation):
    from rules_engine.events import trigger_target_options
    modes = {f'mode-{index+1}': mode for index, mode in enumerate(item.payload['__modal_modes'])
             if trigger_target_options(state, _targeted(selected(item, mode)))}
    if not modes:
        state.log.append(f'{item.label} has no legal mode and is not put on the stack.')
        return False
    state.pending_mechanic_choice = {
        'kind': 'entry_mode', 'player_id': item.controller, '__stack_id': item.id,
        'label': item.label, 'options': list(modes), 'count': 1,
        'option_labels': {key: mode['label'] for key, mode in modes.items()},
        '__modes': modes, '__continuation': deepcopy(continuation),
    }
    state.stack.append(item)
    state.priority_player = item.controller
    state.passed_priority = set()
    return True


def _targeted(item):
    item.payload['__trigger_target_clause'] = item.payload['__counter_mode_clause']
    return item


def view(pending):
    return deepcopy({key: pending[key] for key in
                     ('kind', 'player_id', 'label', 'options', 'option_labels', 'count')})


def finish(state, player_id, action):
    pending = state.pending_mechanic_choice
    if not pending or pending.get('kind') != 'entry_mode' or pending['player_id'] != player_id:
        return False
    mode = pending['__modes'].get(action.get('choice_id'))
    if mode is None:
        return False
    item = next((item for item in state.stack if item.id == pending['__stack_id']), None)
    if item is None or item.controller != player_id or item.effect_key != 'modal_entry':
        return False
    chosen = selected(item, mode)
    from rules_engine.events import trigger_target_options, _publish_ordered_triggers
    if not trigger_target_options(state, _targeted(deepcopy(chosen))):
        return False
    continuation = pending['__continuation']
    state.pending_mechanic_choice = None
    item.effect_key, item.payload = chosen.effect_key, chosen.payload
    _publish_ordered_triggers(state, selected_item=item, **continuation)
    return True
