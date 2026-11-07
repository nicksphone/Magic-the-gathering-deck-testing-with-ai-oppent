"""Source-oracle protocol checks, not gameplay, SQLite or HTTP qualification."""
import hashlib
import json
from pathlib import Path

import pytest

from tests.interface_scope_compatibility import restore_reviewed_source


BACKEND = Path(__file__).parents[1]
RECIPE = json.loads((BACKEND / 'tests/fixtures/interface_scope_compatibility/'
                     'accepted_spectacle_cost_delta.json').read_bytes())['accepted_delta']
OLD = '9294bde1dc08d5cf78df988ae7efeea53ab20d0e65152c94b855a428fb0cca6c'
NEW = '08a45918b5adfd2f09fb8d762e6a6019e064fb77794cdb991399aa8c845516b8'


def sources():
    current = (BACKEND / 'rules_engine/costs.py').read_bytes()
    assert hashlib.sha256(current).hexdigest() == NEW
    lines = current.decode().splitlines(keepends=True)
    hunk, = RECIPE['hunks']
    assert ''.join(lines[hunk['start']:hunk['end']]) == hunk['new']
    lines[hunk['start']:hunk['end']] = hunk['old'].splitlines(keepends=True)
    previous = ''.join(lines).encode()
    assert hashlib.sha256(previous).hexdigest() == OLD
    return previous, current


def test_only_the_reviewed_spectacle_addition_is_reversed():
    previous, current = sources()
    assert restore_reviewed_source('rules_engine/costs.py', current, OLD) == previous
    assert hashlib.sha256(current).hexdigest() == NEW


def test_original_cost_source_and_historical_operands_remain_unchanged():
    previous, _ = sources()
    assert restore_reviewed_source('rules_engine/costs.py', previous, OLD) == previous
    pins = BACKEND / 'tests/fixtures/private_cold_http_interface/reviewed_25ef_pins.json'
    assert hashlib.sha256(pins.read_bytes()).hexdigest() == (
        'd9b3fb5971fec581558fa45d0279a100675a06e81e9758566dc870856beeb4a9')


@pytest.mark.parametrize('mutation', ['outside', 'inside', 'duplicate', 'historical', 'source'])
def test_synthetic_source_mutations_are_not_approved(mutation):
    _, current = sources()
    path, historical = 'rules_engine/costs.py', OLD
    if mutation == 'outside':
        current += b'\n# Unreviewed source mutation, never executed.\n'
    elif mutation == 'inside':
        assert b'life_lost_this_turn.get' in current
        current = current.replace(b'life_lost_this_turn.get', b'life_lost_this_turn.pop', 1)
    elif mutation == 'duplicate':
        current += RECIPE['hunks'][0]['new'].encode()
    elif mutation == 'historical':
        historical = '0' * 64
    else:
        path = 'rules_engine/unreviewed.py'
    with pytest.raises(AssertionError):
        restore_reviewed_source(path, current, historical)
