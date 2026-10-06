"""Unchanged canonical paid triggers must not get free inferred rewards."""
import hashlib
import json
from pathlib import Path

import pytest

from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_death_cycle_ordering_audit import add, cards, cycle_position, receipt, tokens


PATH = Path(__file__).parent / 'fixtures/cycle_discard_limits/canonical.jsonl'
ROWS = {row['name']: row for row in map(json.loads, PATH.read_text().splitlines())}
cards.ROWS.update(ROWS)


def test_canonical_paid_records_are_pinned():
    assert hashlib.sha256(PATH.read_bytes()).hexdigest() == '03a372fe6a2e9a121d10e3f855d6186ac5a85d44f3f771ca45e5a1f324905b38'
    assert set(ROWS) == {'Drake Haven', 'Faith of the Devoted'}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Drake Haven', 'Faith of the Devoted'])
@pytest.mark.parametrize('funded', [False, True])
def test_unimplemented_optional_trigger_payment_reports_without_free_effect(request, seat, name, funded):
    state, source, action = cycle_position(seat, 'Lonely Sandbar')
    add(state, name, seat)
    state.players[seat].mana_pool = {'U': 1, 'C': int(funded)}
    with cards.unchanged_root(state):
        paid = checked_action(state, RulesEngine(), seat, action)
    for _ in range(4):
        if not paid.stack:
            break
        assert resolve_top_of_stack(paid)
    receipt(request, {'action': action, 'canonical': ROWS[name],
                      'resolved': serialize_match_snapshot(paid)})
    assert not tokens(paid, seat)
    assert paid.players[seat].life == paid.players[3-seat].life == 20
    assert paid.players[seat].mana_pool.get('C', 0) == int(funded)
    assert paid.players[seat].mana_pool.get('U', 0) == 0
    assert any('Unsupported optional trigger payment' in line for line in paid.log)
