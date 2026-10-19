"""Canonical paid neighboring routes remain independent of the new grammar."""
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from rules_engine.engine import RulesEngine
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import act, restart
from tests.test_trigger_instruction_compilation_audit import position, passes

FIXTURE = Path(__file__).parent / 'fixtures/trigger_instruction_prefix'
ROWS = {}
for entry in json.loads((FIXTURE / 'provenance.json').read_text())['cards']:
    raw = (FIXTURE / entry['file']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == entry['sha256']
    row = json.loads(raw)
    assert row['oracle_id'] == entry['oracle_id']
    ROWS[row['name']] = row


def source_position(name, seat, pool):
    state, unused, _ = position('Cloudblazer', seat)
    state.players[seat].hand.remove(unused)
    state.cards[unused].move_to_zone(Zone.EXILE)
    state.players[seat].exile.append(unused)
    card = raw_card(state, ROWS[name], seat, Zone.HAND)
    state.players[seat].mana_pool = pool
    return state, card.id


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_krasis_cast_keeps_half_x_dedicated_route(seat, tmp_path):
    state, cid = source_position('Hydroid Krasis', seat, {'C': 4, 'G': 1, 'U': 1})
    life = state.players[seat].life
    state = act(state, seat, {'type': 'cast_spell', 'card_id': cid, 'targets': {'x_value': 4}})
    assert state.stack[-1].effect_key == 'effect_sequence'
    assert '__unsupported_trigger_instruction' not in state.stack[-1].payload
    state = passes(restart(state, tmp_path, 'krasis-cast'))
    assert state.players[seat].life == life + 2 and len(state.players[seat].hand) == 2
    assert state.stack[-1].source_card_id == cid


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('accept', [False, True])
def test_actual_optional_death_observer_keeps_deliberate_choice(seat, accept, tmp_path):
    from tests.test_trigger_instruction_compilation_audit import ROWS as AUDIT_ROWS
    state, cid = source_position('Village Rites', seat, {'B': 1})
    selected = raw_card(state, AUDIT_ROWS['Elvish Visionary'], seat, Zone.BATTLEFIELD)
    observer = raw_card(state, ROWS['Harvester of Souls'], seat, Zone.BATTLEFIELD)
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': cid, 'targets': {},
                            'cost_choice': {'id': 'base', 'sacrifice_card_ids': [selected.id]}})
    # The genuine optional death observer follows an explicitly paid sacrifice.
    moves = RulesEngine().legal_moves(state, seat)
    ordering = next((m for m in moves if m['type'] == 'choose_trigger_order'), None)
    if ordering is not None:
        state = act(state, seat, {'type': 'choose_trigger_order', 'trigger_order': ordering['trigger_order']})
    decisions = 0
    while state.stack:
        moves = RulesEngine().legal_moves(state, state.priority_player)
        choice = next((m for m in moves if m['type'] == 'choose_optional_effect'), None)
        if choice is not None:
            assert state.stack[-1].source_card_id == observer.id
            decisions += 1
            state = act(restart(state, tmp_path, 'optional-choice'), seat,
                        {'type': 'choose_optional_effect', 'stack_id': choice['stack_id'], 'accept': accept})
        else:
            state = passes(state)
    assert state.cards[cid].zone == Zone.GRAVEYARD
    assert state.cards[selected.id].zone == Zone.GRAVEYARD
    assert decisions == 1
    assert len(state.players[seat].hand) == 2 + int(accept)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_targeted_entry_keeps_explicit_public_target(seat, tmp_path):
    from tests.test_trigger_instruction_compilation_audit import ROWS as AUDIT_ROWS
    state, cid = source_position("Man-o'-War", seat, {'C': 2, 'U': 1})
    target = raw_card(state, AUDIT_ROWS['Elvish Visionary'], 3-seat, Zone.BATTLEFIELD)
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    state = passes(act(state, seat, {'type': 'cast_spell', 'card_id': cid, 'targets': {}}))
    # This baseline's legacy return trigger stores an automatic target. This
    # control preserves that route, not a claim of manual target-choice support.
    assert state.stack[-1].payload['target_card_id'] == target.id
    state = passes(restart(state, tmp_path, 'legacy-target-pending'))
    assert state.cards[target.id].zone == Zone.HAND and target.id in state.players[3-seat].hand
    assert state.cards[cid].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_optional_search_entry_keeps_existing_continuation(seat, tmp_path):
    state, cid = source_position('Solemn Simulacrum', seat, {'C': 4})
    state = passes(act(state, seat, {'type': 'cast_spell', 'card_id': cid, 'targets': {}}))
    assert state.stack[-1].effect_key == 'search_library'
    assert '__unsupported_trigger_instruction' not in state.stack[-1].payload
    state = passes(restart(state, tmp_path, 'search-entry-pending'))
    assert state.cards[cid].zone == Zone.BATTLEFIELD
