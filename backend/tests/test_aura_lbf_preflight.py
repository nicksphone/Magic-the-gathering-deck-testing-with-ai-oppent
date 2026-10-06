"""Canonical Aura departures and explicitly controlled no-target/preflight seams."""
from copy import deepcopy

import pytest

from game_state.state import Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.state_based_actions import _apply_attachment_state_checks
from tests.test_noncreature_sba_caller_audit import Harness, receipts
from tests.test_self_graveyard_replacement_audit import snap, restart


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('replacement', [False, True])
@pytest.mark.parametrize('foreign_owner', [False, True])
def test_controlled_no_target_aura_lbf_owner_and_entry(seat, replacement, foreign_owner, receipts, tmp_path):
    h = Harness(seat, 'aura', replacement)
    h.setup()  # Actual paid Pacifism attached to actual paid Bears.
    card = h.state.cards[h.target]
    # Trusted seam only, NOT a naturally executed detach/control-changing episode.
    card.attached_to = None
    if foreign_owner:
        card.owner = 3-seat
    sequence = card.zone_change_sequence
    h.state = restart(h.state, tmp_path, 'controlled-no-target')
    receipts.clear()
    _apply_attachment_state_checks(h.state)
    card = h.state.cards[h.target]
    assert card.zone == (Zone.EXILE if replacement else Zone.GRAVEYARD)
    assert card.id in getattr(h.state.players[card.owner], card.zone.value)
    assert card.id not in h.state.players[seat].battlefield
    assert card.zone_change_sequence == sequence + 1
    own = [r for r in receipts if r['payload'].get('card_id') == card.id]
    assert [r['event'] for r in own] == (['leaves_battlefield'] if replacement
                                       else ['leaves_battlefield', 'enters_graveyard'])
    assert own[0]['zone'] == 'battlefield'
    assert own[0]['lki']['name'] == card.name
    assert own[0]['lki']['controller'] == seat
    assert 'Creature' not in own[0]['lki']['types']
    h.state = restart(h.state, tmp_path, 'controlled-no-target-after')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('stage', ['selection', 'cause'])
def test_controlled_no_target_preflight_failure_is_before_all_departure(seat, stage, monkeypatch, receipts):
    from rules_engine import replacement, zone_actions
    h = Harness(seat, 'aura', False)
    h.setup()
    h.state.cards[h.target].attached_to = None  # Explicit controlled seam.
    before = snap(h.state)
    receipts.clear()
    def unavailable(*args, **kwargs):
        raise ActionRejected('Injected unavailable retained entry plan/cause')
    monkeypatch.setattr(replacement if stage == 'selection' else zone_actions,
                        'select_graveyard_entry_plan' if stage == 'selection' else 'prepare_graveyard_entry_causes',
                        unavailable)
    with pytest.raises(ActionRejected, match='Injected unavailable'):
        _apply_attachment_state_checks(h.state)
    assert snap(h.state) == before
    assert not receipts, 'No LBF/entry before retained replacement preflight succeeds'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('replacement', [False, True])
def test_paid_bounce_selects_and_prepares_while_source_is_still_battlefield(seat, replacement, monkeypatch, receipts):
    from rules_engine import replacement as plans, zone_actions
    h = Harness(seat, 'aura', replacement)
    h.setup()
    select = plans.select_graveyard_entry_plan
    prepare = zone_actions.prepare_graveyard_entry_causes
    order = []
    def retained_select(state, cid, *args, **kwargs):
        if cid == h.target:
            assert state.cards[cid].zone == Zone.BATTLEFIELD
            assert cid in state.players[seat].battlefield
            order.append('select')
        return select(state, cid, *args, **kwargs)
    def retained_prepare(state, selected):
        selected = tuple(selected)
        if any(p.card_id == h.target for p in selected):
            assert h.target in state.players[seat].battlefield
            order.append('cause')
        return prepare(state, selected)
    monkeypatch.setattr(plans, 'select_graveyard_entry_plan', retained_select)
    monkeypatch.setattr(zone_actions, 'prepare_graveyard_entry_causes', retained_prepare)
    receipts.clear()
    h.depart()
    assert order == ['select', 'cause']
    own = [r for r in receipts if r['payload'].get('card_id') == h.target]
    assert own[0]['event'] == 'leaves_battlefield'
    assert own[0]['zone'] == 'battlefield'
    assert own[0]['lki']['controller'] == seat


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_bounce_retained_cause_not_reselected_after_lbf(seat, monkeypatch, receipts):
    from rules_engine import events, zone_actions
    h = Harness(seat, 'aura', True)
    h.setup()
    original = events._collect_triggers
    execute = zone_actions.execute_graveyard_entry
    ran = []
    def inspect_lbf(state, event, payload):
        if event == 'leaves_battlefield' and payload.get('card_id') == h.target:
            assert h.target in state.players[seat].battlefield
            ran.append('lbf')
        return original(state, event, payload)
    def inspect_execution(state, plan, **kwargs):
        if plan.card_id == h.target:
            assert kwargs['prevalidated'] is True
            assert '_prepared_cause' in kwargs
            assert plan.destination == Zone.EXILE
            ran.append('execute')
        return execute(state, plan, **kwargs)
    monkeypatch.setattr(events, '_collect_triggers', inspect_lbf)
    monkeypatch.setattr(zone_actions, 'execute_graveyard_entry', inspect_execution)
    h.depart()
    assert ran == ['lbf', 'execute']
