"""Supplementary cause seam controls; NOT a legal replacement episode."""
from dataclasses import replace

import pytest

from game_state.state import Zone, object_incarnation
from rules_engine.shuffle_actions import (
    prepare_static_replacement_cause, shuffle_library, is_static_replacement_event_cause,
)
from rules_engine.replacement import select_graveyard_entry_plan
from tests.test_self_graveyard_replacement_audit import SELF, position, snap, restart
from tests.test_self_graveyard_replacement_interactions import ROWS
from tests.test_linked_damage_targets import raw_card


def committed(seat, name, stimulus, foreign=False):
    state, card, _, _, _ = position(name, seat, stimulus, foreign)
    receipt = prepare_static_replacement_cause(state, select_graveyard_entry_plan(state, card.id))
    # Controlled commit seam only, until the independently owned real producer is frozen.
    for player in state.players.values():
        for zone in Zone:
            ids = getattr(player, zone.value, [])
            if card.id in ids:
                ids.remove(card.id)
    state.players[card.owner].library.append(card.id)
    card.move_to_zone(Zone.LIBRARY)
    return state, card, receipt


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
@pytest.mark.parametrize('stimulus', ['sacrifice', 'discard', 'mill'])
def test_controlled_commit_retains_pre_reference_and_complete_observers(seat, name, stimulus, tmp_path):
    state, card, receipt = committed(seat, name, stimulus)
    probe = raw_card(state, ROWS['Psychogenic Probe'], 3-seat, Zone.BATTLEFIELD)
    cosi = raw_card(state, ROWS["Cosi's Trickster"], 3-seat, Zone.BATTLEFIELD)
    shuffle_library(state, card.owner, cause=receipt)
    result = [item for item in state.stack if item.source_card_id in {probe.id, cosi.id}]
    assert len(result) == 2
    for item in result:
        cause = item.payload['__shuffle_cause']
        assert cause['kind'] == 'static' and cause['mechanism'] == 'replacement'
        assert 'stack_id' not in cause
        assert cause['source_card_id'] == card.id
        assert cause['controller'] == seat and cause['source_owner'] == card.owner
        assert cause['source_reference'] == {
            'incarnation': receipt.incarnation,
            'zone_change_sequence': receipt.zone_change_sequence,
        }
        assert cause['ability_clause'] == card.oracle_text.splitlines()[cause['ability_index']]
        assert is_static_replacement_event_cause(cause)
    assert object_incarnation(card) == receipt.incarnation
    assert card.zone_change_sequence == receipt.zone_change_sequence + (stimulus != 'mill')
    restart(state, tmp_path, 'controlled-receipt')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
def test_foreign_owner_remains_distinct_from_retained_controller(seat, name):
    state, card, receipt = committed(seat, name, 'sacrifice', True)
    before = snap(state)
    with pytest.raises(ValueError):
        shuffle_library(state, seat, cause=receipt)
    assert snap(state) == before
    shuffle_library(state, 3-seat, cause=receipt)
    assert receipt.controller == seat and receipt.source_owner == 3-seat


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
@pytest.mark.parametrize('stimulus', ['sacrifice', 'discard', 'mill'])
def test_receipt_preparation_is_pure_and_respects_relevant_zone_suppression(seat, name, stimulus):
    state, card, _, _, _ = position(name, seat, stimulus)
    plan = select_graveyard_entry_plan(state, card.id)
    before = snap(state)
    receipt = prepare_static_replacement_cause(state, plan)
    assert snap(state) == before
    raw_card(state, ROWS['Humility'], 3-seat, Zone.BATTLEFIELD)
    before = snap(state)
    if stimulus == 'sacrifice':
        with pytest.raises(ValueError):
            prepare_static_replacement_cause(state, plan)
    else:
        assert prepare_static_replacement_cause(state, plan) == receipt
    assert snap(state) == before


@pytest.mark.parametrize('bad', [
    {}, {'kind': 'static'}, {'kind': 'ability'}, 'static', 1, False,
    'controller', 'source', 'sequence', 'clause', 'duplicate', 'wrong_zone', 'both',
])
def test_malformed_or_stale_cause_rejects_before_rng_log_or_event(bad):
    state, card, receipt = committed(1, 'Darksteel Colossus', 'sacrifice')
    resolving = None
    if bad == 'controller':
        receipt = replace(receipt, controller=2)
    elif bad == 'source':
        receipt = replace(receipt, source_card_id='unknown')
    elif bad == 'sequence':
        receipt = replace(receipt, zone_change_sequence=receipt.zone_change_sequence + 1)
    elif bad == 'clause':
        receipt = replace(receipt, ability_clause='invented')
    elif bad == 'duplicate':
        state.players[1].library.append(card.id)
    elif bad == 'wrong_zone':
        card.zone = Zone.EXILE
    elif bad == 'both':
        resolving = {}
    else:
        receipt = bad
    before = snap(state)
    with pytest.raises(ValueError):
        shuffle_library(state, 1, cause=receipt, resolving_item=resolving)
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_generic_no_cause_keeps_probe_absent_and_cosi_present(seat):
    state, _, _, _, _ = position('Darksteel Colossus', seat, 'sacrifice')
    probe = raw_card(state, ROWS['Psychogenic Probe'], 3-seat, Zone.BATTLEFIELD)
    cosi = raw_card(state, ROWS["Cosi's Trickster"], 3-seat, Zone.BATTLEFIELD)
    shuffle_library(state, seat)
    assert not any(item.source_card_id == probe.id for item in state.stack)
    assert len([item for item in state.stack if item.source_card_id == cosi.id]) == 1
