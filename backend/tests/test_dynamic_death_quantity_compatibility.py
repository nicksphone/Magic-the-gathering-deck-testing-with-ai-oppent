"""Raw canonical compatibility for an already supported two-seat token route."""
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import Step
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_dynamic_death_quantity import add, cards, restart, tokens, write_receipt


DIRECTORY = Path(__file__).parent / 'fixtures/dynamic_death_quantity_compatibility'
RAW = json.loads((DIRECTORY / 'canonical.json').read_text())
cards.ROWS[RAW['name']] = RAW


def test_raw_compatibility_provenance():
    pin = json.loads((DIRECTORY / 'provenance.json').read_text())
    assert pin['http_requests'] == 0 and not pin['facts_modified']
    assert pin['source_records_verified'] == 38690
    assert RAW['id'] == pin['id'] and RAW['oracle_id'] == pin['oracle_id']
    assert hashlib.sha256((DIRECTORY / 'canonical.json').read_bytes()).hexdigest() == pin['canonical_json_sha256']
    encoded = json.dumps(RAW, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    assert hashlib.sha256(encoded).hexdigest() == pin['raw_canonical_sha256']


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_canonical_per_opponent_attack_remains_fixed_count(request, seat):
    state = cards.position(seat)
    state.step = Step.DECLARE_ATTACKERS
    source = add(state, RAW['name'], seat)
    action = {'type': 'attack', 'attackers': [source.id],
              'attack_targets': {source.id: f'player:{3 - seat}'}}
    with cards.unchanged_root(state):
        attacked = checked_action(state, RulesEngine(), seat, action)
    assert len(attacked.stack) == 1
    assert attacked.stack[0].payload['amount'] == 1
    attacked = restart(attacked)
    assert resolve_top_of_stack(attacked)
    generated = tokens(attacked, seat)
    write_receipt(request, {'action': action, 'expected': 1, 'actual': len(generated),
                           'attack_targets': attacked.attack_targets})
    assert len(generated) == 1
    assert generated[0].tapped and generated[0].id in attacked.attackers
    assert attacked.attack_targets[generated[0].id] == f'player:{3 - seat}'
