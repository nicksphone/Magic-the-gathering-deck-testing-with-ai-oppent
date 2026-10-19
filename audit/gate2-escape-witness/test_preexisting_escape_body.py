"""Independent already-admitted canonical body, passive entry observation only."""
import json
import os
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine import entry_counters
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_spell_cost_overlap_investigation import escape_position, cast


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('aspect', ['counters', 'goat'])
def test_already_admitted_complete_escaped_body(monkeypatch, seat, aspect):
    state, _, _, spell, _ = escape_position(seat, initial=4)
    paid = checked_action(state, RulesEngine(), seat, cast(
        spell, from_graveyard=True, cost_choice={'id': 'escape'}))
    item = next(item for item in paid.stack if item.source_card_id == spell.id)
    assert item.payload['__escaped'] is True
    rows = []
    original = entry_counters.prepare_entry_counters

    def observe(state, controller, data, card, resume_effect):
        row = {'source': card.id, 'escaped_entry_flag': data['entry_payload'].get('__escaped'),
               'complete_oracle': card.oracle_text}
        result = original(state, controller, data, card, resume_effect)
        row['entry_counts_after_original'] = dict(data.get('entry_counts', {}))
        rows.append(row)
        return result

    monkeypatch.setattr(entry_counters, 'prepare_entry_counters', observe)
    state = deserialize_match_snapshot(serialize_match_snapshot(paid))
    for _ in range(12):
        if not state.stack:
            break
        state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    assert not state.stack and state.cards[spell.id].zone == Zone.BATTLEFIELD
    goats = [c for c in state.cards.values() if c.is_token and c.zone == Zone.BATTLEFIELD
             and c.owner == seat and c.name == 'Goat']
    receipt = {'stack_escaped_flag': item.payload['__escaped'], 'entry_observations': rows,
               'resolved_counter_map': state.cards[spell.id].counters, 'goat_count': len(goats),
               'snapshot': serialize_match_snapshot(state)}
    phase = os.environ['ESCAPE_CONTROL_PHASE']
    with (Path(__file__).parents[3] / 'evidence' / f'{phase}-{aspect}-{seat}.json').open('x') as out:
        json.dump(receipt, out, indent=2)
    if aspect == 'counters':
        assert state.cards[spell.id].counters.get('+1/+1') == 2
    else:
        assert len(goats) == 1
