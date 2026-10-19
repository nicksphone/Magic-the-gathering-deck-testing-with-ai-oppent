"""Actual whole-graveyard versus separate departures with canonical Tomb."""
from copy import deepcopy

import pytest

from ai.information import decision_view, is_unknown
from game_state.state import Step, Zone
from rules_engine.card_types import is_token_card
from rules_engine.continuous import has_keyword
from rules_engine.engine import RulesEngine
from tests.test_builtin_metadata_refresh import repo
from tests.generic_import_fixtures import client as base_client
from tests.test_direct_graveyard_bypass_audit import ROWS as DIRECT, client, install, main_controller_snapshot, public_private_restore
from tests.test_kozilek_graveyard_trigger_audit import FRESH as RESPONSES, opposing_priority
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import ROWS
from tests.test_self_graveyard_replacement_audit import act, position, restart, snap
from tests.test_spell_admission_safety_http import sql_facts
from tests.readiness_rules_seam_support import normalize
from tests.test_simultaneous_graveyard_entry_audit import FRESH, KOZILEK, passes


def position_with_tomb(seat):
    state, kozilek, source, _, action = position(KOZILEK, seat, 'discard')
    other = raw_card(state, DIRECT['Doomed Traveler'], seat, Zone.HAND)
    tomb = raw_card(state, FRESH['Desecrated Tomb'], seat, Zone.BATTLEFIELD)
    action['targets'] = {'x_value': 2}
    action['cost_choice']['discard_card_ids'] = [kozilek.id, other.id]
    state.priority_stops = {pid: set(Step) for pid in (1, 2)}
    return state, kozilek.id, other.id, tomb.id, source.id, action


def bat_ids(state, seat):
    return [cid for cid in state.players[seat].battlefield
            if is_token_card(state.cards[cid]) and 'bat' in state.cards[cid].name.lower()]


def resolve_tomb_token(state, seat, tomb_id):
    assert state.stack[-1].source_card_id == tomb_id
    assert state.stack[-1].effect_key == 'create_token'
    state = passes(state)
    return state


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mode', ['whole_batch', 'two_events'])
def test_actual_tomb_batch_or_separate_count_and_canonical_bat(seat, mode, tmp_path):
    state, koz, other, tomb, source, action = position_with_tomb(seat)
    if mode == 'two_events':
        cremate = raw_card(state, RESPONSES['Cremate'], 3-seat, Zone.HAND)
        state.players[3-seat].mana_pool = {'B': 1}
    state = act(state, seat, action)
    assert state.stack[-1].source_card_id == koz
    assert {koz, other}.issubset(state.players[seat].graveyard)
    assert not any(item.source_card_id == tomb for item in state.stack)
    state = restart(state, tmp_path, 'before-whole-shuffle')
    if mode == 'two_events':
        state = opposing_priority(state, 3-seat)
        state = act(state, 3-seat, {'type': 'cast_spell', 'card_id': cremate.id,
                                  'targets': {'target_card_id': other}})
        state = passes(state)
        assert state.cards[other].zone == Zone.EXILE
        assert len([item for item in state.stack if item.source_card_id == tomb]) == 1
        state = resolve_tomb_token(state, seat, tomb)
        assert len(bat_ids(state, seat)) == 1
        state = restart(state, tmp_path, 'separate-first-bat')
    state = passes(state)
    assert state.cards[koz].zone == Zone.LIBRARY
    if mode == 'whole_batch':
        assert state.cards[other].zone == Zone.LIBRARY
    assert not state.players[seat].graveyard
    assert len([item for item in state.stack if item.source_card_id == tomb]) == 1, \
        'One-or-more observer needs ONE receipt for the whole creature departure batch'
    state = restart(state, tmp_path, 'one-receipt-after-whole-shuffle')
    state = resolve_tomb_token(state, seat, tomb)
    expected = 1 if mode == 'whole_batch' else 2
    assert len(bat_ids(state, seat)) == expected
    for cid in bat_ids(state, seat):
        card = state.cards[cid]
        assert str(card.power) == str(card.toughness) == '1'
        assert has_keyword(state, cid, 'flying')
        assert card.colors == ['B']
    assert any(item.source_card_id == source for item in state.stack)
    view, _ = decision_view(state, 3-seat, RulesEngine().legal_moves(state, 3-seat))
    assert all(is_unknown(view.cards[cid]) for cid in state.players[seat].hand + state.players[seat].library)
    restart(state, tmp_path, 'resolved-canonical-bat')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mode', ['whole_batch', 'two_events'])
def test_http_actual_paid_tomb_episode_atomic_root_sql_and_restart(repo, client, seat, mode, tmp_path):
    for row in [*ROWS.values(), *FRESH.values(), *RESPONSES.values()]:
        repo.upsert_card(normalize(row))
    state, koz, other, tomb, _, action = position_with_tomb(seat)
    if mode == 'two_events':
        cremate = raw_card(state, RESPONSES['Cremate'], 3-seat, Zone.HAND)
        state.players[3-seat].mana_pool = {'B': 1}
    controller = install(repo, client, state)

    def send(actor, intent):
        response = client.post('/matches/' + controller.state.id + '/action',
                               json={'player_id': actor, 'action': intent})
        assert response.status_code == 200, response.text

    def pass_pair():
        for _ in range(2):
            send(controller.state.priority_player, {'type': 'pass_priority'})

    before = snap(controller.state), deepcopy(main_controller_snapshot(controller)), sql_facts(repo)
    rejected = client.post('/matches/' + controller.state.id + '/action', json={'player_id': 3-seat, 'action': action})
    assert rejected.status_code == 422
    assert (snap(controller.state), main_controller_snapshot(controller), sql_facts(repo)) == before
    send(seat, action)
    assert controller.state.stack[-1].source_card_id == koz
    controller = public_private_restore(repo, client, controller, seat, tmp_path)
    if mode == 'two_events':
        if controller.state.priority_player != 3-seat:
            send(controller.state.priority_player, {'type': 'pass_priority'})
        send(3-seat, {'type': 'cast_spell', 'card_id': cremate.id, 'targets': {'target_card_id': other}})
        pass_pair()
        assert controller.state.cards[other].zone == Zone.EXILE
        assert len([item for item in controller.state.stack if item.source_card_id == tomb]) == 1
        pass_pair()
        assert len(bat_ids(controller.state, seat)) == 1
        controller = public_private_restore(repo, client, controller, seat, tmp_path)
    pass_pair()
    assert controller.state.cards[koz].zone == Zone.LIBRARY
    assert len([item for item in controller.state.stack if item.source_card_id == tomb]) == 1
    controller = public_private_restore(repo, client, controller, seat, tmp_path)
    pass_pair()
    assert len(bat_ids(controller.state, seat)) == (1 if mode == 'whole_batch' else 2)
    public_private_restore(repo, client, controller, seat, tmp_path)
