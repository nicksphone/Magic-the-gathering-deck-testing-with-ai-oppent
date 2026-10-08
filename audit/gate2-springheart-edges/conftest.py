"""Readonly context trace: delegate every result to the unchanged real validator."""
import json
import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def actual_entry_context_trace(monkeypatch, request):
    from rules_engine import entry_counters
    original = entry_counters.entry_counter_context_matches

    def observed(state, payload):
        result = original(state, payload)
        context = payload.get('__counter_entry_context') or {}
        targets = payload.get('entry_targets') or []
        index = payload.get('entry_target_index')
        row = {'node': request.node.nodeid, 'actual_result': result,
               'entry_target_index': index, 'target_card_id': payload.get('target_card_id'),
               'counter': payload.get('counter'), 'context_recipient_id': context.get('recipient_id'),
               'batch_recipient_ids': [target.get('card_id', target.get('candidate', {}).get('id'))
                                       for target in targets],
               'entry_completion_payload': payload.get('entry_completion_payload')}
        with (Path(os.environ['MTG_SPRINGHEART_EVIDENCE'])/'entry-context-actual.jsonl').open('a') as stream:
            stream.write(json.dumps(row, sort_keys=True)+'\n')
        return result

    monkeypatch.setattr(entry_counters, 'entry_counter_context_matches', observed)
