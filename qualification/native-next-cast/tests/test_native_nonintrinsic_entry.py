"""Full canonical non-intrinsic recipient: no manufactured source/frame/body."""
from pathlib import Path
import hashlib
import json
import os

import pytest

from game_state.state import Zone
from rules_engine.continuous import effective_combat_stats
from test_native_next_creature_entry import SOURCES, source_ready, choose_type, finish_entry
from tests.test_graveyard_self_activation_product import raw_card, act, snapshot


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', SOURCES)
def test_paid_canonical_nonintrinsic_recipient_reaches_native_entry(request, seat, family):
    root = Path(os.environ['MTG_ISOLATED_TEST_ROOT']) / 'backend/tests/fixtures/global_flash_timing_audit'
    raw_bytes = (root / 'grizzly-bears.json').read_bytes()
    entry = next(row for row in json.loads((root / 'provenance.json').read_text())['cards']
                 if row['file'] == 'grizzly-bears.json')
    assert hashlib.sha256(raw_bytes).hexdigest() == entry['sha256']
    raw = json.loads(raw_bytes)
    assert raw['oracle_id'] == entry['oracle_id']
    state, sid = source_ready(seat, family)
    if family == SOURCES[0]:
        state = choose_type(state, seat, 'bear')
    card = raw_card(state, raw, seat, Zone.HAND)
    state.players[seat].mana_pool = {'G': 1, 'C': 1}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': card.id, 'targets': {}})
    assert len(state.stack) == 2 and not state.pending_entry_counters
    assert state.stack[-1].effect_key == 'bind_creature_spell_entry_counter'
    assert state.stack[-1].payload['__native_cast']['stack_id'] == state.stack[-2].id
    paid = snapshot(state)
    path = Path(os.environ['MTG_NONINTRINSIC_EVIDENCE']) / (
        hashlib.sha256(request.node.nodeid.encode()).hexdigest() + '.json')
    try:
        result = finish_entry(state, seat)
    except Exception as error:
        with path.open('x') as stream:
            json.dump({'family': family, 'seat': seat, 'source_id': sid, 'paid': paid,
                       'recipient_raw': raw, 'provenance': entry,
                       'failure_type': type(error).__name__, 'failure': str(error)}, stream, indent=2)
        raise
    assert result.cards[card.id].zone == Zone.BATTLEFIELD
    assert result.cards[card.id].counters['+1/+1'] == 1
    assert effective_combat_stats(result, card.id) == (3, 3)
    assert not result.pending_entry_counters
