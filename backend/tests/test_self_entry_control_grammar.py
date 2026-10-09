"""Compiler-only clause controls, not paid or complete-card certification."""
from copy import deepcopy

import pytest

from tests.agent_control_facts import ROWS
from tests.test_source_linked_exile import position, raw_card, Zone
from rules_engine.events import _trigger_from_oracle


@pytest.mark.parametrize('variant', [
    'canonical', 'legacy_named', 'renamed', 'self_permanent',
    'unknown_sentence', 'unknown_parenthetical', 'duration',
    'optional', 'wrong_source', 'wrong_entering', 'two_control_lines',
])
def test_complete_self_entry_control_clause(variant):
    state, other = position(1)
    row = deepcopy(ROWS['Agent of Treachery'])
    instruction = 'When this creature enters, gain control of target permanent.'
    if variant == 'legacy_named':
        instruction = f"When {row['name']} enters the battlefield, gain control of target permanent."
    elif variant == 'renamed':
        row['name'] = 'Independent Entry Source'
        instruction = 'When Independent Entry Source enters, gain control of target permanent.'
    elif variant == 'self_permanent':
        instruction = instruction.replace('this creature', 'this permanent')
    elif variant == 'unknown_sentence':
        instruction += ' Unknown instruction.'
    elif variant == 'unknown_parenthetical':
        instruction += ' (Unknown instruction.)'
    elif variant == 'duration':
        instruction = instruction.replace('permanent.', 'permanent until end of turn.')
    elif variant == 'optional':
        instruction = instruction.replace('gain control', 'you may gain control')
    elif variant == 'wrong_source':
        instruction = instruction.replace('this creature', 'Unrelated Source')
    elif variant == 'two_control_lines':
        instruction += '\n' + instruction
    source = raw_card(state, row, 1, Zone.HAND)
    before = deepcopy(state)
    trigger = _trigger_from_oracle(
        state, source.id, 1, instruction, 'entry compiler control',
        'enters_battlefield', {'card_id': other if variant == 'wrong_entering' else source.id},
    )
    accepted = variant in {'canonical', 'legacy_named', 'renamed', 'self_permanent'}
    assert (trigger['effect_key'] == 'change_control') == accepted
    if accepted:
        assert trigger['controller'] == 1
        assert 'new_controller' not in trigger['payload']
        assert trigger['payload']['until_end_of_turn'] is False
        assert 'target_card_id' not in trigger['payload']
        assert trigger['payload']['__trigger_full_clause'] == instruction
    else:
        assert trigger['effect_key'] == 'noop'
    assert state.cards[source.id].controller == before.cards[source.id].controller
    assert state.players[1].battlefield == before.players[1].battlefield
    assert state.players[2].battlefield == before.players[2].battlefield
