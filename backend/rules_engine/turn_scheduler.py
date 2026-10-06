"""Resolved extra turns and phase visits; no private card identities or RNG."""
from copy import deepcopy
import re

from game_state.state import Step


PHASE_STEPS = {
    'beginning': [Step.UNTAP, Step.UPKEEP, Step.DRAW],
    'precombat_main': [Step.PRECOMBAT_MAIN],
    'combat': [Step.BEGIN_COMBAT, Step.DECLARE_ATTACKERS, Step.DECLARE_BLOCKERS,
               Step.COMBAT_DAMAGE, Step.END_COMBAT],
    'postcombat_main': [Step.POSTCOMBAT_MAIN],
    'end_step': [Step.END_STEP],
    'cleanup': [Step.CLEANUP],
}
NORMAL_PHASES = tuple(PHASE_STEPS)
TURN = re.compile(r'(target player takes|take) an extra turn after this one\.?', re.I)
COMBAT = re.compile(
    r'untap all creatures you control\.\s*after this main phase, there is an additional '
    r'combat phase followed by an additional main phase\.\s*activate only as a sorcery\.?', re.I)


def instruction(text):
    """Only full admitted schemas, never a substring of extra instructions."""
    from rules_engine.oracle_text import without_reminder_text
    text = without_reminder_text(text or '').strip()
    match = TURN.fullmatch(text)
    if match:
        return 'target' if match[1].lower().startswith('target') else 'controller'
    if COMBAT.fullmatch(text):
        return 'combat_main'
    return None


def _normal_plan(state):
    plan = []
    for kind in NORMAL_PHASES:
        plan.append({'visit': state.next_phase_visit, 'kind': kind, 'group': 0})
        state.next_phase_visit += 1
    return plan


def ensure_plan(state):
    if state.normal_turn_successor is None:
        state.normal_turn_successor = 3 - state.active_player
    if not state.phase_plan:
        state.phase_plan = _normal_plan(state)
    # Legacy fixtures may directly position an ordinary turn between actions.
    if state.step not in PHASE_STEPS[state.phase_plan[state.phase_cursor]['kind']]:
        if any(row['group'] for row in state.phase_plan):
            raise ValueError('Step contradicts queued phase visit')
        state.phase_cursor = next(i for i, row in enumerate(state.phase_plan)
                                  if state.step in PHASE_STEPS[row['kind']])


def advance(state):
    """Return true at a completed turn boundary; cleanup is gated by caller."""
    ensure_plan(state)
    steps = PHASE_STEPS[state.phase_plan[state.phase_cursor]['kind']]
    index = steps.index(state.step)
    if index + 1 < len(steps):
        state.step = steps[index + 1]
    elif state.phase_cursor + 1 < len(state.phase_plan):
        state.phase_cursor += 1
        state.step = PHASE_STEPS[state.phase_plan[state.phase_cursor]['kind']][0]
    else:
        if state.extra_turns:
            state.active_player = state.extra_turns.pop()['recipient']
        else:
            state.active_player = state.normal_turn_successor
            state.normal_turn_successor = 3 - state.active_player
        state.phase_plan = _normal_plan(state)
        state.phase_cursor = 0
        state.step = Step.UNTAP
        return True
    return False


def resolve_turn(state, controller, payload):
    recipient = payload.get('target_player', controller)
    if type(recipient) is not int or recipient not in state.players:
        raise ValueError('Invalid extra-turn recipient')
    ensure_plan(state)
    state.extra_turns.append({'recipient': recipient, 'anchor_turn': state.turn,
                             'ordinal': state.next_schedule_ordinal,
                             'source_card_id': payload.get('__source_card_id')})
    state.next_schedule_ordinal += 1


def resolve_combat_main(state, controller, payload):
    from rules_engine.named_counters import untap_permanent
    from rules_engine.type_effects import effective_types
    for cid in list(state.players[controller].battlefield):
        card = state.cards[cid]
        if card.controller == controller and 'Creature' in effective_types(state, card):
            untap_permanent(state, cid)
    # The untap still happens if a copied ability resolves outside a main phase.
    if state.step not in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN}:
        return
    ensure_plan(state)
    group = state.next_schedule_ordinal
    state.next_schedule_ordinal += 1
    visits = []
    for kind in ('combat', 'postcombat_main'):
        visits.append({'visit': state.next_phase_visit, 'kind': kind, 'group': group})
        state.next_phase_visit += 1
    state.phase_plan[state.phase_cursor + 1:state.phase_cursor + 1] = visits


FIELDS = ('normal_turn_successor', 'extra_turns', 'next_schedule_ordinal',
          'phase_plan', 'phase_cursor', 'next_phase_visit')


def snapshot(state):
    return {'version': 1, **{name: deepcopy(getattr(state, name)) for name in FIELDS}}


def restore(state, data):
    if (not isinstance(data, dict) or type(data.get('version')) is not int
            or data['version'] != 1 or set(data) != {'version', *FIELDS}):
        raise ValueError('Invalid scheduler snapshot')
    def integer(value, minimum=0):
        return type(value) is int and value >= minimum
    successor = data['normal_turn_successor']
    if (successor is not None and (type(successor) is not int or successor not in (1, 2))
            or not integer(data['next_schedule_ordinal'], 1)
            or not integer(data['next_phase_visit'], 1)
            or not integer(data['phase_cursor'])
            or not isinstance(data['extra_turns'], list)
            or not isinstance(data['phase_plan'], list)):
        raise ValueError('Invalid scheduler counters')
    ordinals = []
    for row in data['extra_turns']:
        if (not isinstance(row, dict) or set(row) != {'recipient', 'anchor_turn', 'ordinal', 'source_card_id'}
                or type(row['recipient']) is not int or row['recipient'] not in state.players
                or not integer(row['anchor_turn'], 1) or row['anchor_turn'] > state.turn
                or not integer(row['ordinal'], 1)
                or row['source_card_id'] is not None and not isinstance(row['source_card_id'], str)):
            raise ValueError('Invalid extra-turn entry')
        ordinals.append(row['ordinal'])
    if ordinals != sorted(set(ordinals)) or any(x >= data['next_schedule_ordinal'] for x in ordinals):
        raise ValueError('Invalid extra-turn order')
    plan = data['phase_plan']
    visits = []
    normal = []
    groups = []
    i = 0
    while i < len(plan):
        row = plan[i]
        if (not isinstance(row, dict) or set(row) != {'visit', 'kind', 'group'}
                or not isinstance(row['kind'], str) or row['kind'] not in PHASE_STEPS
                or not integer(row['visit'], 1)
                or not integer(row['group'])):
            raise ValueError('Invalid phase visit')
        visits.append(row['visit'])
        if row['group'] == 0:
            normal.append(row['kind'])
        elif row['kind'] == 'combat':
            if (i == 0 or plan[i - 1]['kind'] not in {'precombat_main', 'postcombat_main'}
                    or i + 1 >= len(plan) or not isinstance(plan[i + 1], dict)
                    or plan[i + 1].get('kind') != 'postcombat_main'
                    or plan[i + 1].get('group') != row['group']):
                raise ValueError('Invalid combat/main insertion group')
            groups.append(row['group'])
        elif (row['kind'] != 'postcombat_main' or i == 0
              or plan[i - 1]['kind'] != 'combat' or plan[i - 1]['group'] != row['group']):
            raise ValueError('Invalid extra phase')
        i += 1
    if (len(visits) != len(set(visits)) or any(x >= data['next_phase_visit'] for x in visits)
            or len(groups) != len(set(groups)) or set(groups).intersection(ordinals)
            or any(x >= data['next_schedule_ordinal'] for x in groups)):
        raise ValueError('Invalid scheduler identities')
    if plan:
        if (tuple(normal) != NORMAL_PHASES or data['normal_turn_successor'] is None
                or data['phase_cursor'] >= len(plan)
                or state.step not in PHASE_STEPS[plan[data['phase_cursor']]['kind']]):
            raise ValueError('Invalid phase cursor')
    elif (data['phase_cursor'] or data['extra_turns'] or data['normal_turn_successor'] is not None
          or data['next_phase_visit'] != 1 or data['next_schedule_ordinal'] != 1):
        raise ValueError('Missing queued phase plan')
    for name in FIELDS:
        setattr(state, name, deepcopy(data[name]))
