"""Bounded complete cost-bearing modal instructions, independent of card names."""
from dataclasses import dataclass, replace
import re


COPY = ('Copy target instant spell, sorcery spell, activated ability, or triggered '
        'ability. You may choose new targets for the copy.')
CHANGE = 'Change the target of target spell or ability with a single target.'


@dataclass(frozen=True)
class Mode:
    text: str
    generic: int
    effect: str


def is_spree(text):
    return bool(re.match(r'^\s*spree\b', text or '', re.I))


def parse(text):
    if not is_spree(text) or len(text) > 12000:
        return None
    lines = text.strip().splitlines()
    if len(lines) != 3 or not re.fullmatch(
            r'Spree(?: \(Choose one or more additional costs\.\))?', lines[0], re.I):
        return None
    modes = []
    for line, instruction, effect in zip(lines[1:], (COPY, CHANGE),
                                         ('spree_copy', 'spree_change_target')):
        match = re.fullmatch(r'\+ \{([1-9][0-9]?)\} [\u2014-] (.+)', line)
        if not match or match[2] != instruction:
            return None
        modes.append(Mode(match[2], int(match[1]), effect))
    return tuple(modes)


def selected(modes, targets, *, preview=False):
    one, many = targets.get('mode_text'), targets.get('mode_texts')
    if one is not None and many:
        raise ValueError('Use one mode selection representation')
    values = many or ([one] if one is not None else [])
    if (not isinstance(values, list) or any(not isinstance(x, str) for x in values)
            or len(values) > len(modes) or len(set(values)) != len(values)
            or any(x not in {m.text for m in modes} for x in values)
            or not values and not preview):
        raise ValueError('Select one or more distinct printed modes')
    return [m for m in modes if m.text in values]


def priced(option, modes):
    return replace(option, mana_cost=option.mana_cost + '{' + str(sum(m.generic for m in modes)) + '}')


def unpriced_base(option, modes):
    """Invert only the exact suffix added by priced in the same mode context."""
    extra = '{' + str(sum(m.generic for m in modes)) + '}'
    if not modes or not option.mana_cost.endswith(extra):
        raise ValueError('Spree cost option lacks its exact pricing suffix')
    return option.mana_cost[:-len(extra)]


def compile_instruction(card, targets):
    modes = parse(card.oracle_text)
    if modes is None:
        return 'noop', {'__unsupported_instruction': card.oracle_text}
    try:
        chosen = selected(modes, targets, preview=True)
    except ValueError:
        return 'noop', {'__unsupported_instruction': card.oracle_text}
    effects = []
    for mode in chosen:
        target = (targets.get('mode_targets') or {}).get(mode.text, targets)
        effects.append({'effect_key': mode.effect, 'mode_text': mode.text,
                        'payload': {'target_stack_id': target.get('target_stack_id')}})
    return 'effect_sequence', {'effects': effects}


def target_instances(item):
    announced = item.payload.get('__announced_targets') or {
        k: item.payload[k] for k in ('target_player', 'target_card_id', 'target_stack_id')
        if item.payload.get(k) is not None}

    def count(data):
        return (sum(data.get(k) is not None for k in
                    ('target_player', 'target_card_id', 'target_stack_id'))
                + len(data.get('target_card_ids') or [])
                + len(data.get('target_distribution') or {})
                + sum(count(x) for x in (data.get('mode_targets') or {}).values()))
    return count(announced)


def hints(state, card, targets):
    from rules_engine.targeting import stack_object_kind, stack_source_card
    modes = parse(card.oracle_text)
    if modes is None:
        return {'unsupported_resolution': ['unsupported complete Spree body']}
    try:
        chosen = selected(modes, targets, preview=True)
    except ValueError:
        return {'modes': [m.text for m in modes], 'choose_one_or_more_modes': True,
                'stack_targets': [], 'unsupported_resolution': ['invalid Spree selection']}
    candidates = []
    for item in state.stack:
        kind = stack_object_kind(state, item)
        source = stack_source_card(state, item)
        copyable = kind in {'activated', 'triggered'} or (
            kind == 'spell' and source is not None
            and set(source.types).intersection({'Instant', 'Sorcery'}))
        eligible = all(copyable if m.effect == 'spree_copy'
                       else kind in {'spell', 'activated', 'triggered'} and target_instances(item) == 1
                       for m in chosen)
        if eligible and (copyable or target_instances(item) == 1):
            candidates.append({'id': item.id, 'label': item.label})
    return {'modes': [m.text for m in modes], 'choose_one_or_more_modes': True,
            'stack_targets': candidates}


def resolve_copy(state, controller, payload):
    from effects.handlers import copy_spell, copy_ability
    from rules_engine.targeting import stack_object_kind, stack_source_card
    item = next((x for x in state.stack if x.id == payload.get('target_stack_id')), None)
    if item is None:
        return
    kind = stack_object_kind(state, item)
    if kind == 'spell':
        source = stack_source_card(state, item)
        if source is None or not set(source.types).intersection({'Instant', 'Sorcery'}):
            return
    elif kind not in {'activated', 'triggered'}:
        return
    (copy_spell if kind == 'spell' else copy_ability)(
        state, controller, {**payload, 'may_choose_new_targets': True})


def offer_change(state, controller, payload):
    from effects.handlers import _offer_copy_target_choice
    item = next((x for x in state.stack if x.id == payload.get('target_stack_id')), None)
    if item is None or target_instances(item) != 1:
        return
    _offer_copy_target_choice(state, item.controller, item, original=True)
    pending = state.pending_mechanic_choice
    if pending:
        pending['options'] = [x for x in pending['options'] if x != 'keep']
        if not pending['options']:
            state.pending_mechanic_choice = None
            return
        pending.update(kind='spree_target_change', player_id=controller,
                       label='Change the single target', original_controller=item.controller)


def valid_change(state, pending, choice):
    from copy import deepcopy
    if choice == 'keep':
        return False
    item = next((x for x in state.stack if x.id == pending['stack_id']), None)
    if item is None or target_instances(item) != 1 or item.controller != pending['original_controller']:
        return False
    trial = deepcopy(state)
    trial.pending_mechanic_choice = None
    offer_change(trial, pending['player_id'], {'target_stack_id': item.id})
    fresh = trial.pending_mechanic_choice
    return bool(fresh and choice in fresh['options'])
