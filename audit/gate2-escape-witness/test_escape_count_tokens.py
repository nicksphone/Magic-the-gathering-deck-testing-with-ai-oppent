"""Non-card token boundaries of the actual entry branch; not gameplay evidence."""
import ast
import inspect
import re

import pytest

from rules_engine.entry_counters import prepare_entry_counters
from rules_engine.oracle_effects import _parse_count_token


def escape_count_pattern():
    patterns = [node.args[0].value for node in ast.walk(ast.parse(
        inspect.getsource(prepare_entry_counters)))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == 'search' and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
        and node.args[0].value.startswith('escapes with ')]
    assert len(patterns) == 1
    return re.compile(patterns[0], re.I)


@pytest.mark.parametrize('token,amount', [
    ('a', 1), ('an', 1), ('one', 1), ('two', 2), ('three', 3), ('four', 4),
    ('five', 5), ('six', 6), ('seven', 7), ('eight', 8), ('nine', 9), ('ten', 10),
    ('0', 0), ('17', 17), ('TWO', 2)])
def test_existing_count_vocabulary(token, amount):
    match = escape_count_pattern().fullmatch(f'escapes with {token} +1/+1 counters')
    assert match and _parse_count_token(match[1]) == amount


@pytest.mark.parametrize('token', ['zero', 'eleven', '-1', '2.5', 'twosome', 'unknown'])
def test_unknown_token_never_reaches_fallback_parser(token):
    assert escape_count_pattern().search(f'escapes with {token} +1/+1 counters') is None
