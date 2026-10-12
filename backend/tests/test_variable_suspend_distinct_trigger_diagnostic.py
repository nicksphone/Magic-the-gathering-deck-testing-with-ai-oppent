"""Paid suspend plus the real counter emitter; no fabricated event or trigger row."""
from copy import deepcopy

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine import suspend
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.variable_suspend_support import NAMES, RAW, position


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('seat', [1, 2])
def test_paid_last_counter_emits_distinct_keyword_and_printed_card_ability(name, seat, monkeypatch):
    state, cid = position(name, seat)
    before = serialize_match_snapshot(state)
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'suspend', 'card_id': cid, 'x_value': 1})
    assert state.cards[cid].zone == Zone.EXILE and state.cards[cid].counters['time'] == 1
    assert state.players[seat].mana_pool.get('C', 0) == 2
    assert state.players[seat].mana_pool.get(RAW[name]['colors'][0], 0) == 0
    assert not state.stack and state.spells_cast_this_turn[seat] == 0
    calls = []
    original = suspend.collect_triggers

    def observe(current, event, payload):
        result = original(current, event, payload)
        if current is state and event == 'time_counters_removed':
            calls.append((deepcopy(payload), deepcopy(result)))
        return result

    monkeypatch.setattr(suspend, 'collect_triggers', observe)
    assert suspend.remove_time_counters(state, cid) == 1
    assert state.cards[cid].counters.get('time', 0) == 0
    assert len(calls) == 1
    payload, rows = calls[0]
    assert payload == {'card_id': cid, 'before': 1, 'after': 0}
    keyword = [row for row in rows if row['effect_key'] == 'suspend_cast_trigger']
    printed = [row for row in rows if row['effect_key'] != 'suspend_cast_trigger']
    assert len(rows) == 2 and len(keyword) == len(printed) == 1
    assert all(row['source_card_id'] == cid and row['controller'] == seat for row in rows)
    assert keyword[0]['payload']['sequence'] == state.cards[cid].zone_change_sequence
    expected = {'Aeon Chronicler': 'draw_cards', 'Detritivore': 'destroy_permanent'}[name]
    assert printed[0]['effect_key'] == expected
    clause = next(line for line in RAW[name]['oracle_text'].splitlines()
                  if line.startswith('Whenever a time counter is removed'))
    assert printed[0]['payload']['__trigger_full_clause'] == clause
    assert state.cards[cid].oracle_text == RAW[name]['oracle_text']
    assert serialize_match_snapshot(state) != before
