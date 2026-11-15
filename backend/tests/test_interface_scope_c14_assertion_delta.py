"""Byte-exact inverse of the published C14 assertion; never execute old rules."""
import ast
from copy import deepcopy
import hashlib
from pathlib import Path
import re

import pytest

from tests import interface_scope_compatibility as api


MODULE = 'test_oracle_effects.py'
FUNCTION = 'test_light_up_the_stage_style_exiles_cards_with_temporary_play_permission'
IDENTITY = MODULE + ':' + FUNCTION
# From commit38389136 and its parent, not a digest blessed from the working tree.
POST = 'a248fcf85394619977cb9c929a1b54a81a4989b26ba82591ca1c61abfb20adca'
PRE = '7da9b68bcddbcb870ec13b88c0a316b9dbb7a4a9b972249e4cb608490e2a66f4'
ORIGINAL = 'e9d9990d7aee2bca33fa220ddea2eadfc4ad63bda7d8982c80e116fd0629812a'
NEW = (
    '    from rules_engine.card_faces import ordinary_exile_permission\n'
    '    from rules_engine.source_linked_exile import reference\n'
    '    assert state.players[1].exile_play_durations[top_id] == {\n'
    "        'version': 1, 'duration': 'controller_next_turn', 'grant_turn': state.turn,\n"
    "        'reference': reference(state.cards[top_id])}\n"
    '    assert ordinary_exile_permission(state, 1, top_id)')
OLD = '    assert state.players[1].exile_play_until[top_id] == state.turn + 1'


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def source():
    return Path(__file__).with_name(MODULE).read_text()


def function(text):
    nodes = [n for n in ast.parse(text).body
             if isinstance(n, ast.FunctionDef) and n.name == FUNCTION]
    assert len(nodes) == 1
    return ast.get_source_segment(text, nodes[0])


def stages():
    current = function(source())
    assert digest(current) == POST and current.count(NEW) == 1
    previous = current.replace(NEW, OLD, 1)
    assert digest(previous) == PRE == api.FINITE['functions'][IDENTITY]['new_sha256']
    historical = api._restore(previous, api.FINITE['functions'][IDENTITY])
    assert digest(historical) == ORIGINAL == api.EXPECTED_FUNCTIONS[IDENTITY]
    return current, previous, historical


def outside_approved_functions(text):
    recipes = {**api.FINITE['functions'], **api.FIXTURE_INVERSES,
               api.SMOTHERING_IDENTITY: api.SMOTHERING_INVERSE}
    names = {identity.split(':')[1] for identity in recipes
             if identity.split(':')[0] == MODULE}
    segments = [ast.get_source_segment(text, node) for node in ast.parse(text).body
                if isinstance(node, ast.FunctionDef) and node.name in names]
    for segment in segments:
        text = text.replace(segment, '<protected-function>', 1)
    return text


@pytest.mark.parametrize('stage', range(3), ids=['C14', 'previous-canonical', 'historical'])
def test_published_c14_and_both_prior_stages_reconstruct_the_same_original(stage):
    current, previous, historical = stages()
    text = source().replace(current, (current, previous, historical)[stage], 1)
    result = api.restore_printed_protocol_source(MODULE, text)
    assert function(result) == historical
    assert digest(function(result)) == ORIGINAL
    assert outside_approved_functions(result) == outside_approved_functions(text)


@pytest.mark.parametrize('line', range(6))
def test_each_new_assertion_line_rejects_a_valid_python_byte_mutation(line):
    current, _, _ = stages()
    lines = NEW.splitlines(keepends=True)
    old = lines[line]
    # Mutate inside the AST operand, including its last line (not a trailing comment).
    mutated = re.sub(r'^([ \t]*\S+)', r'\1 ', old, count=1)
    changed = current.replace(old, mutated, 1)
    assert changed != current
    ast.parse(changed)
    with pytest.raises(AssertionError):
        api.restore_printed_protocol_source(MODULE, source().replace(current, changed, 1))


@pytest.mark.parametrize('change', ['outside', 'historical', 'duplicate', 'missing'])
def test_c14_inverse_does_not_admit_unreviewed_function_changes(change):
    current, previous, historical = stages()
    if change == 'outside':
        changed = current.replace('    top_id =', '    top_id  =', 1)
        text = source().replace(current, changed, 1)
    elif change == 'historical':
        changed = historical.replace('    top_id =', '    top_id  =', 1)
        text = source().replace(current, changed, 1)
    elif change == 'duplicate':
        text = source() + '\n\n' + current + '\n'
    else:
        text = source().replace(current, '', 1)
    assert text != source()
    with pytest.raises(AssertionError):
        api.restore_printed_protocol_source(MODULE, text)


def test_published_assertion_bridge_keeps_all_original_goldens_and_recipes():
    current, previous, historical = stages()
    assert len(api.EXPECTED_FUNCTIONS) == 60 and len(api.FINITE['functions']) == 14
    assert api.FINITE['functions'][IDENTITY]['old_sha256'] == ORIGINAL
    assert api.FINITE['functions'][IDENTITY]['new_sha256'] == PRE
    assert digest(current) == POST and digest(previous) == PRE and digest(historical) == ORIGINAL


@pytest.mark.parametrize('mutation', ['old_sha', 'new_sha', 'old_body', 'new_body', 'start', 'end', 'hunks'])
def test_corrupt_c14_inverse_cannot_reconstruct_history(monkeypatch, mutation):
    stages()
    recipe = deepcopy(api.CONTROLLER_NEXT_TURN_INVERSE)
    if mutation in {'old_sha', 'new_sha'}:
        recipe[mutation + '256'] = '0' * 64
    elif mutation in {'old_body', 'new_body'}:
        recipe['hunks'][0][mutation.split('_')[0]] += '# unauthorized\n'
    elif mutation in {'start', 'end'}:
        recipe['hunks'][0][mutation] += 1
    else:
        recipe['hunks'] = None
    monkeypatch.setattr(api, 'CONTROLLER_NEXT_TURN_INVERSE', recipe)
    with pytest.raises((AssertionError, TypeError)):
        api.restore_printed_protocol_source(MODULE, source())


@pytest.mark.parametrize('start,end', [(False, 1), (0, True), (-1, 1), (0, 2)])
def test_invalid_undo_spans_are_not_python_slice_aliases(start, end):
    # Synthetic text protocol, not a fabricated card or historical source operand.
    recipe = {'old_sha256': digest('old'),
              'hunks': [{'start': start, 'end': end, 'new': 'new', 'old': 'old'}]}
    with pytest.raises(AssertionError):
        api._restore('new', recipe)
