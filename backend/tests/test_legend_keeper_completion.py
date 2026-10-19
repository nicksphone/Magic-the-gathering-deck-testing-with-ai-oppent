"""Canonical paid keeper episodes and explicitly controlled simultaneous/stale seams."""
from copy import deepcopy
import json

import pytest

from ai.information import decision_view, is_unknown
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.state_based_actions import apply_state_based_actions, finish_legend_keeper_choice
from tests import test_human_legend_keeper_audit as audit
from tests.test_combat_graveyard_caller_audit import receipts, client, base_client, repo
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import snap, restart


def controlled_groups(seat, *, copies=2, foreign=False, replacement=False, other_controller=False):
    # Trusted canonical initial board, NOT an executed simultaneous entry episode.
    h = audit.Legend(seat, audit.ISAMARU)
    groups = []
    for name in audit.FAMILIES:
        actor = 3-seat if other_controller and name == 'Progenitus' else seat
        ids = [raw_card(h.state, audit.ROWS[name], actor, Zone.BATTLEFIELD).id
               for _ in range(copies)]
        if foreign and name == audit.ISAMARU:
            h.state.cards[ids[0]].owner = 3-seat
        groups.append(ids)
    if replacement:
        h.rip = raw_card(h.state, audit.ROWS['Rest in Peace'], seat, Zone.BATTLEFIELD).id
    apply_state_based_actions(h.state)
    return h, groups


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('change', ['zone_roundtrip', 'controller', 'new_duplicate'])
def test_paid_pending_keeper_rejects_controlled_stale_group(seat, change, receipts, tmp_path):
    h = audit.episode(seat, audit.ISAMARU, receipts, tmp_path)
    audit.require_keeper(h)
    card = h.state.cards[h.old]
    if change == 'zone_roundtrip':
        card.move_to_zone(Zone.EXILE)
        card.move_to_zone(Zone.BATTLEFIELD)
    elif change == 'controller':
        h.state.players[seat].battlefield.remove(h.old)
        h.state.players[3-seat].battlefield.append(h.old)
        card.controller = 3-seat
    else:
        raw_card(h.state, audit.ROWS[audit.ISAMARU], seat, Zone.BATTLEFIELD)
    h.state = restart(h.state, tmp_path, 'controlled-stale-keeper')
    audit.reject_without_mutation(h, seat, {'type': 'choose_mechanic', 'card_ids': [h.new]})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('copies', [2, 3])
@pytest.mark.parametrize('other_controller', [False, True])
def test_controlled_multi_group_all_keepers_precede_any_departure(
        seat, copies, other_controller, receipts, tmp_path):
    h, groups = controlled_groups(seat, copies=copies, foreign=True,
                                 other_controller=other_controller)
    ids = sum(groups, [])
    sequences = {cid: h.state.cards[cid].zone_change_sequence for cid in ids}
    keepers = []
    receipts.clear()
    for index in range(2):
        pending = h.state.pending_mechanic_choice
        assert pending['kind'] == 'legend_keeper' and pending['count'] == 1
        keeper = pending['options'][-1]
        keepers.append(keeper)
        h.state = restart(h.state, tmp_path, 'multi-group-' + str(index))
        audit.reject_without_mutation(h, 3-pending['player_id'],
                                     {'type': 'choose_mechanic', 'card_ids': [keeper]})
        h.act(pending['player_id'], {'type': 'choose_mechanic', 'card_ids': [keeper]})
        if index == 0:
            assert all(h.state.cards[cid].zone == Zone.BATTLEFIELD for cid in ids)
            assert not receipts, 'No LBF/entry/death before every keeper selection'
    losers = [cid for cid in ids if cid not in keepers]
    assert not h.state.pending_mechanic_choice and not h.state.pending_replacement_choice
    for cid in ids:
        card = h.state.cards[cid]
        assert card.zone_change_sequence == sequences[cid] + (cid in losers)
        assert card.zone == (Zone.BATTLEFIELD if cid in keepers else
                             Zone.LIBRARY if card.name == 'Progenitus' else Zone.GRAVEYARD)
        if cid in losers:
            assert cid in getattr(h.state.players[card.owner], card.zone.value)
            assert card.last_known_battlefield['controller'] in (1, 2)
    events = [r for r in receipts if r['payload'].get('card_id') in losers]
    assert [r['event'] for r in events[:len(losers)]] == ['leaves_battlefield'] * len(losers)
    for cid in losers:
        assert [r['event'] for r in events if r['payload']['card_id'] == cid] == (
            ['leaves_battlefield'] if h.state.cards[cid].name == 'Progenitus' else
            ['leaves_battlefield', 'enters_graveyard', 'permanent_dies', 'creature_dies'])
    restart(h.state, tmp_path, 'all-group-departures')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('destination', ['exile', 'library'])
def test_controlled_three_copies_replacement_choices_are_complete_before_lbf(
        seat, destination, receipts, tmp_path):
    h, groups = controlled_groups(seat, copies=3, replacement=True)
    ids = sum(groups, [])
    keepers = []
    receipts.clear()
    while h.state.pending_mechanic_choice:
        pending = h.state.pending_mechanic_choice
        keeper = pending['options'][-1]
        keepers.append(keeper)
        h.act(pending['player_id'], {'type': 'choose_mechanic', 'card_ids': [keeper]})
    for index in range(2):
        pending = h.state.pending_replacement_choice
        assert pending['resume_kind'] == 'legend_keeper_die'
        target = pending['target_card_id']
        assert {option['source_id'] for option in pending['options']} == {h.rip, target}
        assert all(h.state.cards[cid].zone == Zone.BATTLEFIELD for cid in ids)
        assert not receipts
        h.state = restart(h.state, tmp_path, 'three-copy-choice-' + str(index))
        source = h.rip if destination == 'exile' else target
        h.act(seat, {'type': 'choose_replacement', 'replacement_source_id': source})
    assert all(h.state.cards[cid].zone == Zone.BATTLEFIELD for cid in keepers)
    for cid in groups[1][:-1]:
        assert h.state.cards[cid].zone == Zone(destination)
    assert all(h.state.cards[cid].zone == Zone.EXILE for cid in groups[0][:-1])
    assert not any(r['event'] in ('creature_dies', 'permanent_dies', 'enters_graveyard')
                   for r in receipts)
    restart(h.state, tmp_path, 'three-copy-complete')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('change', ['source_roundtrip', 'target_roundtrip', 'new_replacement'])
def test_paid_replacement_revalidates_retained_sources_and_group(seat, change, receipts, tmp_path):
    h = audit.episode(seat, 'Progenitus', receipts, tmp_path, replacement=True)
    h.act(seat, {'type': 'choose_mechanic', 'card_ids': [h.new]})
    if change == 'source_roundtrip':
        card = h.state.cards[h.rip]
        card.move_to_zone(Zone.HAND)
        card.move_to_zone(Zone.BATTLEFIELD)
    elif change == 'target_roundtrip':
        card = h.state.cards[h.old]
        card.move_to_zone(Zone.EXILE)
        card.move_to_zone(Zone.BATTLEFIELD)
    else:
        raw_card(h.state, audit.ROWS['Rest in Peace'], seat, Zone.BATTLEFIELD)
    h.state = restart(h.state, tmp_path, 'controlled-stale-replacement')
    receipts.clear()
    audit.reject_without_mutation(h, seat,
                                 {'type': 'choose_replacement', 'replacement_source_id': h.rip})
    assert not receipts


@pytest.mark.parametrize('seat', [1, 2])
def test_controlled_cause_failure_precedes_every_loser_departure(seat, monkeypatch, receipts):
    from rules_engine import zone_actions
    h, groups = controlled_groups(seat, copies=3)
    first = h.state.pending_mechanic_choice
    h.act(first['player_id'], {'type': 'choose_mechanic', 'card_ids': [first['options'][-1]]})
    pending = h.state.pending_mechanic_choice
    before = snap(h.state)
    receipts.clear()
    def unavailable(state, plans):
        plans = tuple(plans)
        assert len(plans) == 4
        assert all(state.cards[p.card_id].zone == Zone.BATTLEFIELD for p in plans)
        raise ActionRejected('Injected retained cause failure')
    monkeypatch.setattr(zone_actions, 'prepare_graveyard_entry_causes', unavailable)
    with pytest.raises(ActionRejected, match='Injected retained cause'):
        finish_legend_keeper_choice(h.state, pending['player_id'],
                                   {'type': 'choose_mechanic', 'card_ids': [pending['options'][-1]]})
    assert snap(h.state) == before and not receipts


@pytest.mark.parametrize('seat', [1, 2])
def test_keeper_internal_context_is_not_client_authoritative(seat, receipts, tmp_path):
    h = audit.episode(seat, audit.ISAMARU, receipts, tmp_path)
    pending = deepcopy(h.state.pending_mechanic_choice)
    h.act(seat, {'type': 'choose_mechanic', 'card_ids': [h.new],
                'legend_context': {'keepers': {'0': h.old}, 'plans': {}},
                'legend_group_index': 999})
    assert h.state.cards[h.new].zone == Zone.BATTLEFIELD
    assert h.state.cards[h.old].zone == Zone.GRAVEYARD
    assert pending['legend_context']['keepers'] == {}


@pytest.mark.parametrize('seat', [1, 2])
def test_automatic_policy_without_human_keeper_flags_still_keeps_first(seat, receipts):
    h = audit.Legend(seat, audit.ISAMARU)
    ids = [raw_card(h.state, audit.ROWS[audit.ISAMARU], seat, Zone.BATTLEFIELD).id
           for _ in range(2)]
    h.state.mechanic_choice_players = set()
    apply_state_based_actions(h.state)
    assert not h.state.pending_mechanic_choice
    assert h.state.cards[ids[0]].zone == Zone.BATTLEFIELD
    assert h.state.cards[ids[1]].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('destination', ['library', 'exile'])
def test_actual_http_replacement_restart_wholeview_and_private_atomic(
        repo, client, seat, destination, receipts, tmp_path):
    import main
    h = audit.episode(seat, 'Progenitus', receipts, tmp_path, replacement=True,
                      client=client, repo=repo)
    audit.require_keeper(h)
    moves = RulesEngine().legal_moves(h.state, seat)
    assert len(moves) == 1 and moves[0]['count'] == 1
    assert moves[0]['legend_context'] == h.state.pending_mechanic_choice['legend_context']
    assert set(moves[0]['legend_context']['groups'][0]['references']) == {h.old, h.new}
    assert RulesEngine().legal_moves(h.state, 3-seat) == []
    actor_view, _ = decision_view(h.state, seat, moves)
    assert all(is_unknown(actor_view.cards[cid]) for cid in h.state.players[3-seat].hand)
    assert all(is_unknown(actor_view.cards[cid]) for player in h.state.players.values() for cid in player.library)
    h.act(seat, {'type': 'choose_mechanic', 'card_ids': [h.new]})
    expected = snap(h.state)
    main.ACTIVE_MATCHES.pop(h.state.id)
    get = client.get('/matches/' + h.state.id)
    assert get.status_code == 200
    h.controller = main.ACTIVE_MATCHES[h.state.id]
    h.state = h.controller.state
    assert snap(h.state) == expected
    h.state = restart(h.state, tmp_path, 'http-real-replacement')
    h.persist()
    action = {'type': 'choose_replacement',
              'replacement_source_id': h.old if destination == 'library' else h.rip}
    audit.reject_without_mutation(h, 3-seat, action)
    audit.reject_without_mutation(h, seat, {**action, 'replacement_source_id': 'not-offered'})
    h.act(seat, action)
    assert h.state.cards[h.new].zone == Zone.BATTLEFIELD
    assert h.state.cards[h.old].zone == Zone(destination)
    assert not h.state.pending_mechanic_choice and not h.state.pending_replacement_choice
    expected = snap(h.state)
    main.ACTIVE_MATCHES.pop(h.state.id)
    assert client.get('/matches/' + h.state.id).status_code == 200
    h.controller = main.ACTIVE_MATCHES[h.state.id]
    assert snap(h.controller.state) == expected
    (tmp_path / 'wholeview-abi.json').write_text(json.dumps({'moves': moves, 'after': expected}))


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_http_stale_keeper_is_sql_root_atomic(repo, client, seat, receipts, tmp_path):
    h = audit.episode(seat, audit.ISAMARU, receipts, tmp_path, client=client, repo=repo)
    # Controlled departure/return while real pending, not claimed as a causal HTTP episode.
    h.state.cards[h.old].move_to_zone(Zone.EXILE)
    h.state.cards[h.old].move_to_zone(Zone.BATTLEFIELD)
    h.persist()
    audit.reject_without_mutation(h, seat, {'type': 'choose_mechanic', 'card_ids': [h.new]})


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_http_internal_context_fields_are_rejected(repo, client, seat, receipts, tmp_path):
    h = audit.episode(seat, audit.ISAMARU, receipts, tmp_path, client=client, repo=repo)
    audit.reject_without_mutation(h, seat, {'type': 'choose_mechanic', 'card_ids': [h.new],
                                         'legend_context': {'keepers': {'0': h.old}}})
    audit.reject_without_mutation(h, seat, {'type': 'choose_mechanic', 'card_ids': [h.new],
                                         'legend_group_index': 999})
    h.act(seat, {'type': 'choose_mechanic', 'card_ids': [h.new]})
    assert h.state.cards[h.new].zone == Zone.BATTLEFIELD
    assert h.state.cards[h.old].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_http_stale_replacement_is_sql_root_atomic(repo, client, seat, receipts, tmp_path):
    h = audit.episode(seat, 'Progenitus', receipts, tmp_path, replacement=True,
                      client=client, repo=repo)
    h.act(seat, {'type': 'choose_mechanic', 'card_ids': [h.new]})
    # Trusted source roundtrip; not an executed source-removal HTTP episode.
    h.state.cards[h.rip].move_to_zone(Zone.HAND)
    h.state.cards[h.rip].move_to_zone(Zone.BATTLEFIELD)
    h.state = restart(h.state, tmp_path, 'http-stale-replacement-source')
    h.persist()
    receipts.clear()
    audit.reject_without_mutation(h, seat,
                                 {'type': 'choose_replacement', 'replacement_source_id': h.rip})
    assert not receipts


@pytest.mark.parametrize('seat', [1, 2])
def test_controlled_competing_destinations_without_continuation_fail_closed(seat, receipts, tmp_path):
    h = audit.episode(seat, 'Progenitus', receipts, tmp_path, replacement=True)
    h.state.replacement_choice_required = False
    before = snap(h.state)
    receipts.clear()
    with pytest.raises(ActionRejected, match='^Human legend replacement selection requires an enabled continuation$'):
        finish_legend_keeper_choice(h.state, seat,
                                   {'type': 'choose_mechanic', 'card_ids': [h.new]})
    assert snap(h.state) == before and not receipts


@pytest.mark.parametrize('seat', [1, 2])
def test_controlled_earlier_replacement_selection_stays_retained_until_batch(seat, receipts, tmp_path):
    h, groups = controlled_groups(seat, copies=3, replacement=True)
    while h.state.pending_mechanic_choice:
        pending = h.state.pending_mechanic_choice
        h.act(pending['player_id'], {'type': 'choose_mechanic', 'card_ids': [pending['options'][-1]]})
    first_target = h.state.pending_replacement_choice['target_card_id']
    h.act(seat, {'type': 'choose_replacement', 'replacement_source_id': first_target})
    assert h.state.pending_replacement_choice['target_card_id'] != first_target
    assert all(h.state.cards[cid].zone == Zone.BATTLEFIELD for cid in sum(groups, []))
    h.state.cards[first_target].move_to_zone(Zone.EXILE)
    h.state.cards[first_target].move_to_zone(Zone.BATTLEFIELD)
    h.state = restart(h.state, tmp_path, 'stale-earlier-selection')
    receipts.clear()
    audit.reject_without_mutation(h, seat,
                                 {'type': 'choose_replacement', 'replacement_source_id': h.rip})
    assert not receipts


@pytest.mark.parametrize('seat', [1, 2])
def test_controlled_mixed_human_automatic_groups_retain_automatic_first_policy(seat, receipts):
    h, groups = controlled_groups(seat, other_controller=True)
    # Rebuild a controlled same-position prompt with only the actual human actor.
    h.state.pending_mechanic_choice = None
    h.state.mechanic_choice_players = {seat}
    apply_state_based_actions(h.state)
    pending = h.state.pending_mechanic_choice
    assert pending['player_id'] == seat and pending['options'] == groups[0]
    assert all(h.state.cards[cid].zone == Zone.BATTLEFIELD for cid in sum(groups, []))
    h.act(seat, {'type': 'choose_mechanic', 'card_ids': [groups[0][-1]]})
    assert h.state.cards[groups[0][-1]].zone == Zone.BATTLEFIELD
    assert h.state.cards[groups[1][0]].zone == Zone.BATTLEFIELD
    assert h.state.cards[groups[1][-1]].zone == Zone.LIBRARY


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('continuation', [False, True])
def test_controlled_same_destination_sources_need_explicit_human_selection(
        seat, continuation, receipts, tmp_path):
    h = audit.episode(seat, audit.ISAMARU, receipts, tmp_path, replacement=True)
    # An additional full canonical source is a controlled board seam, not a paid second RiP.
    second = raw_card(h.state, audit.ROWS['Rest in Peace'], seat, Zone.BATTLEFIELD).id
    h.state.replacement_choice_required = continuation
    before = snap(h.state)
    receipts.clear()
    action = {'type': 'choose_mechanic', 'card_ids': [h.new]}
    if not continuation:
        with pytest.raises(ActionRejected, match='replacement'):
            finish_legend_keeper_choice(h.state, seat, action)
        assert snap(h.state) == before and not receipts
    else:
        h.act(seat, action)
        pending = h.state.pending_replacement_choice
        assert {option['source_id'] for option in pending['options']} == {h.rip, second}
        assert all(h.state.cards[cid].zone == Zone.BATTLEFIELD for cid in [h.old, h.new])
        assert not receipts
        h.state = restart(h.state, tmp_path, 'same-destination-explicit-source')
        h.act(seat, {'type': 'choose_replacement', 'replacement_source_id': second})
        assert h.state.cards[h.old].zone == Zone.EXILE
        assert h.state.cards[h.new].zone == Zone.BATTLEFIELD
