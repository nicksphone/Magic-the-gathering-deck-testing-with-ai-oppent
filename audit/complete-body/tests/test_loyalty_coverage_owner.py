"""The direct static coverage owner requires the entire raw loyalty compiler."""
import pytest
from rules_engine.closed_loyalty import compile_body
from rules_engine.continuous import conditional_static_clause_coverage


def surface(name, cost, instruction, pronoun):
    return (f'Flash\nAs long as {name} entered this turn, you may activate {pronoun} '
            f'loyalty abilities any time you could cast an instant.\n{cost}: {instruction}')


@pytest.mark.parametrize('name', ['The Wandering Emperor', 'Reusable Permission Walker'])
@pytest.mark.parametrize('cost', ['+7', '-4', '0', '-X'])
@pytest.mark.parametrize('instruction', ['Draw three cards.', 'You gain 5 life.',
    'Put two +1/+1 counters on target creature. It gains flying until end of turn.',
    'Create three 3/4 blue Bird creature tokens with flying.'])
@pytest.mark.parametrize('pronoun', ['her', 'his', 'its', 'their'])
def test_full_generic_raw_body_delegates_accounted_entry_permission(name, cost, instruction, pronoun):
    text = surface(name, cost, instruction, pronoun)
    assert compile_body(text, name) is not None
    assert conditional_static_clause_coverage(text, name) == []


@pytest.mark.parametrize('tail', ['\nThen perform an unspecified operation.',
    ' Then perform an unspecified operation.', ' (Unknown reminder.)',
    '\nWhenever an unspecified event occurs, perform an unspecified operation.',
    '\nAs long as an unspecified condition holds, perform an unspecified operation.'])
@pytest.mark.parametrize('name', ['The Wandering Emperor', 'Reusable Permission Walker'])
def test_unaccounted_full_body_keeps_original_static_labels(tail, name):
    text = surface(name, '+7', 'Draw three cards.', 'their') + tail
    assert compile_body(text, name) is None
    reasons = {reason for row in conditional_static_clause_coverage(text, name) for reason in row['reasons']}
    assert {'unsupported conditional static predicate', 'unsupported conditional static instruction'} <= reasons


@pytest.mark.parametrize('name', ['The Wandering Emperor', 'Reusable Permission Walker'])
@pytest.mark.parametrize('mode', ['permission-only', 'unknown-ability', 'flash-reminder', 'wrong-source'])
def test_permission_line_alone_is_not_a_capability_waiver(name, mode):
    text = surface(name, '+1', 'Draw a card.', 'its')
    if mode == 'permission-only':
        text = text.rsplit('\n', 1)[0]
    elif mode == 'unknown-ability':
        text = text.replace('Draw a card.', 'Perform an unspecified operation.')
    elif mode == 'flash-reminder':
        text = text.replace('Flash\n', 'Flash (Unknown reminder.)\n')
    else:
        text = text.replace(f'as long as {name}', 'as long as A Different Walker')
        text = text.replace(f'As long as {name}', 'As long as A Different Walker')
    assert compile_body(text, name) is None
    assert conditional_static_clause_coverage(text, name)
