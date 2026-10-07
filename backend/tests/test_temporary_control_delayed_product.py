"""Real paid control spells and targetless, counterable control-loss triggers."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from ai.information import decision_view
from game_state.state import Step, Zone, object_incarnation
from rules_engine.continuous import has_keyword
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import _infer_temporary_control_instruction
from tests.test_temporary_control_lifecycle_audit import (
    ROWS, position, cast, advance, passes, restart, act, snap, raw_card, assert_private,
)
from tests.test_kozilek_graveyard_trigger_audit import FRESH


@pytest.fixture(autouse=True)
def no_sqlite_or_network(monkeypatch):
    import socket
    import sqlite3

    def denied(*args, **kwargs):
        raise AssertionError('This cohort is SQLite/network-free')

    monkeypatch.setattr(sqlite3, 'connect', denied)
    monkeypatch.setattr(socket.socket, 'connect', denied)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign', [False, True])
def test_cleanup_control_returns_before_real_delayed_tap_resolves(seat, foreign, tmp_path):
    state, spell, target = position(seat, 'ray-of-command', foreign)
    reference = [object_incarnation(state.cards[target]), state.cards[target].zone_change_sequence]
    state = cast(state, seat, spell, target)
    source_reference = [object_incarnation(state.cards[spell]), state.cards[spell].zone_change_sequence]
    assert state.stack[-1].payload['mana_spent'] == 4
    state = passes(restart(state, tmp_path, 'paid-ray'))
    assert state.cards[target].controller == seat and not state.cards[target].tapped
    assert has_keyword(state, target, 'haste')
    record = state.delayed_triggers[-1]
    assert record['controller'] == seat and record['source_card_id'] == spell
    assert record['payload']['__delayed_source_reference'] == dict(
        zip(('incarnation', 'zone_change_sequence'), source_reference))
    state = advance(restart(state, tmp_path, 'waiting-loss'))
    assert state.step == Step.CLEANUP and state.cleanup_repeat_required
    assert state.cards[target].controller == 3-seat and not state.cards[target].tapped
    assert not has_keyword(state, target, 'haste')
    trigger = state.stack[-1]
    assert trigger.effect_key == 'control_loss_tap' and trigger.controller == seat
    assert trigger.source_card_id == spell and trigger.payload['card_id'] == target
    assert [trigger.payload['incarnation'], trigger.payload['zone_change_sequence']] == reference
    assert 'target_card_id' not in trigger.payload and '__announced_targets' not in trigger.payload
    state = passes(restart(state, tmp_path, 'cleanup-delayed-stack'))
    assert state.cards[target].tapped and not state.stack and not state.delayed_triggers
    assert_private(state)
    state = passes(state)
    assert state.step == Step.CLEANUP and not state.cleanup_repeat_required
    state = passes(state)
    assert state.step != Step.CLEANUP


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_other_ray_causes_earlier_loss_and_counterable_original_controller_tap(seat, tmp_path):
    state, spell, target = position(seat, 'ray-of-command')
    other = 3-seat
    second = raw_card(state, ROWS['ray-of-command'], other, Zone.HAND).id
    state.players[other].mana_pool = {'C': 3, 'U': 1}
    state = passes(cast(state, seat, spell, target))
    state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert state.priority_player == other
    state = cast(state, other, second, target)
    state = passes(state)
    assert state.cards[target].controller == other and not state.cards[target].tapped
    assert state.stack[-1].effect_key == 'control_loss_tap'
    assert state.stack[-1].controller == seat and state.stack[-1].source_card_id == spell
    state = passes(restart(state, tmp_path, 'early-loss'))
    assert state.cards[target].tapped
    state = advance(state)
    # Both until-end-of-turn layers end simultaneously; the second effect does
    # not restore the first effect's already-expired temporary controller.
    assert state.cards[target].controller == other and not state.temporary_control_changes
    assert not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_cloudshift_does_not_tap_reentered_creature_from_old_delayed_record(seat, tmp_path):
    state, spell, target = position(seat, 'ray-of-command')
    blink = raw_card(state, ROWS['cloudshift'], seat, Zone.HAND).id
    state = passes(cast(state, seat, spell, target))
    sequence = state.cards[target].zone_change_sequence
    state = passes(cast(state, seat, blink, target))
    assert state.cards[target].zone_change_sequence == sequence + 2
    assert state.cards[target].controller == seat and not state.cards[target].tapped
    assert state.stack[-1].effect_key == 'control_loss_tap'
    state = passes(restart(state, tmp_path, 'old-object-tap-not-new-object'))
    assert not state.cards[target].tapped and not state.delayed_triggers


@pytest.mark.parametrize('seat', [1, 2])
def test_real_stifle_counters_cleanup_delayed_tap_not_control_expiry(seat, tmp_path):
    state, spell, target = position(seat, 'ray-of-command')
    stifle = raw_card(state, FRESH['Stifle'], seat, Zone.HAND).id
    island = json.loads((Path(__file__).parents[1] / 'card_data/builtin_oracle_seed.json')
                        .read_text())['cards']['Island']
    land = raw_card(state, island, seat, Zone.BATTLEFIELD).id
    state = advance(passes(cast(state, seat, spell, target)))
    trigger_id = state.stack[-1].id
    state = act(state, seat, {'type': 'tap_land_for_mana', 'card_id': land, 'color': 'U'})
    state = act(state, seat, {'type': 'cast_spell', 'card_id': stifle,
                            'targets': {'target_stack_id': trigger_id}, 'cost_choice': {'id': 'base'}})
    state = passes(restart(state, tmp_path, 'real-stifle-delayed-tap'))
    assert not state.stack and not state.cards[target].tapped
    assert state.cards[target].controller == 3-seat and not state.delayed_triggers
    assert state.cards[stifle].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_real_response_blink_fizzles_announced_old_target_without_control_reward(seat):
    state, spell, target = position(seat, 'ray-of-command')
    other = 3-seat
    blink = raw_card(state, ROWS['cloudshift'], other, Zone.HAND).id
    state = cast(state, seat, spell, target)
    state = act(state, seat, {'type': 'pass_priority'})
    state = passes(cast(state, other, blink, target))
    assert state.cards[target].controller == other
    state = passes(state)
    assert state.cards[target].controller == other and not state.delayed_triggers
    assert not has_keyword(state, target, 'haste') and state.cards[spell].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_pending_delayed_record_does_not_expose_opposing_hidden_spell_identity(seat):
    state, spell, target = position(seat, 'ray-of-command')
    hidden = raw_card(state, ROWS['act-of-treason'], 3-seat, Zone.HAND).id
    other_hidden = raw_card(state, ROWS['cloudshift'], 3-seat, Zone.LIBRARY).id
    state = passes(cast(state, seat, spell, target))
    changed = deepcopy(state)
    for cid, replacement_id in ((hidden, other_hidden), (other_hidden, hidden)):
        replacement = deepcopy(state.cards[replacement_id])
        original = changed.cards[cid]
        replacement.id, replacement.zone = cid, original.zone
        replacement.zone_change_sequence = original.zone_change_sequence
        changed.cards[cid] = replacement
    before = snap(state)
    view, moves = decision_view(state, seat, RulesEngine().legal_moves(state, seat))
    other, alternatives = decision_view(changed, seat, RulesEngine().legal_moves(changed, seat))
    assert snap(view) == snap(other) and moves == alternatives and snap(state) == before
    assert_private(state)


@pytest.mark.parametrize('suffix', [' Draw a card.', ' If you do, draw a card.',
                                   ' You may draw a card.', ' Instead, exile it.'])
@pytest.mark.parametrize('seat', [1, 2])
def test_complete_new_grammar_unknown_tail_cannot_grant_partial_control_or_untap(suffix, seat):
    text = ROWS['ray-of-command']['oracle_text'] + suffix
    key, data = _infer_temporary_control_instruction(text.lower(), seat, {'target_card_id': 'chosen'})
    assert key == 'noop' and data == {'__unsupported_instruction': text.lower()}


@pytest.mark.parametrize('seat', [1, 2])
def test_existing_act_compiler_not_claimed_by_new_complete_instruction_family(seat):
    assert _infer_temporary_control_instruction(ROWS['act-of-treason']['oracle_text'], seat,
                                                {'target_card_id': 'chosen'}) is None
