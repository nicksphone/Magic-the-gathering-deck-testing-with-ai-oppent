"""Actual public temporary-control actions with owned memory/file SQL only."""
from copy import deepcopy

import pytest

from game_state.state import Zone
from rules_engine.continuous import has_keyword
from tests.generic_import_fixtures import client as base_client
from tests.test_builtin_metadata_refresh import repo
from tests.test_batch_graveyard_publication_audit import client, assert_private
from tests.test_cloudshift_compound_audit import cold_sql
from tests.test_paid_counter_family_audit import http_position
from tests.test_spell_admission_safety_http import sql_facts
from tests.test_temporary_control_lifecycle_audit import FAMILIES, position, advance, snap


def install(repo, client, seat, family, foreign=False):
    import main
    controller, _, _, path = http_position(repo, client, seat, 'Fertilid')
    state, spell, target = position(seat, family, foreign)
    state.id = controller.state.id
    controller.state = state
    main._persist_active_match(repo, controller)
    return state, spell, target, path


def send(client, path, actor, action):
    import main
    response = client.post(path + '/action', json={'player_id': actor, 'action': action})
    assert response.status_code == 200, response.text
    return main.ACTIVE_MATCHES[path.rsplit('/', 1)[-1]].state


def resolve(client, path, state):
    for _ in range(2):
        state = send(client, path, state.priority_player, {'type': 'pass_priority'})
    return state


def request(spell, target):
    return {'type': 'cast_spell', 'card_id': spell, 'cost_choice': {'id': 'base'},
            'targets': {'target_card_id': target}}


def restore(repo, state):
    import main
    controller = main.ACTIVE_MATCHES[state.id]
    before = snap(state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
    cold_sql(repo, state.id, before[:2])
    main.ACTIVE_MATCHES.pop(state.id)
    main._restore_active_matches(repo, state.id)
    controller = main.ACTIVE_MATCHES[state.id]
    assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
    return controller.state


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
def test_actual_paid_http_control_cold_restore_then_natural_end_of_turn(
        repo, client, seat, family):
    state, spell, target, path = install(repo, client, seat, family, foreign=(seat == 2))
    owner = state.cards[target].owner
    sequence = state.cards[target].zone_change_sequence
    state = send(client, path, seat, request(spell, target))
    assert state.stack[-1].controller == seat
    assert state.stack[-1].payload['mana_spent'] == (4 if family == 'ray-of-command' else 3)
    state = resolve(client, path, restore(repo, state))
    card = state.cards[target]
    assert card.zone == Zone.BATTLEFIELD and card.owner == owner and card.controller == seat
    assert card.zone_change_sequence == sequence and not card.tapped
    assert card.summoning_sick and has_keyword(state, target, 'haste')
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert_private(state)
    if family == 'ray-of-command':
        retained_delay = deepcopy(state.delayed_triggers[-1])
    state = advance(restore(repo, state),
                    send=lambda root, actor, action: send(client, path, actor, action))
    assert state.cards[target].owner == owner and state.cards[target].controller == 3-seat
    assert target in state.players[3-seat].battlefield
    assert state.cards[target].summoning_sick and not has_keyword(state, target, 'haste')
    if family == 'ray-of-command':
        from game_state.state import Step
        from rules_engine.targeting import spell_cant_be_countered
        assert state.step == Step.CLEANUP and state.cleanup_repeat_required
        assert not state.cards[target].tapped
        trigger = state.stack[-1]
        assert trigger.effect_key == 'control_loss_tap' and trigger.controller == seat
        assert trigger.source_card_id == spell == retained_delay['source_card_id']
        assert trigger.payload['card_id'] == target
        for key in ('incarnation', 'zone_change_sequence', '__delayed_source_reference'):
            assert trigger.payload[key] == retained_delay['payload'][key]
        assert trigger.targets == [] and 'target_card_id' not in trigger.payload
        assert not spell_cant_be_countered(state, trigger)
        state = resolve(client, path, restore(repo, state))
    assert state.cards[target].tapped == (family == 'ray-of-command')
    assert not state.temporary_control_changes
    assert_private(restore(repo, state))


@pytest.mark.parametrize('seat', [1, 2])
def test_invalid_http_selected_target_is_entire_root_controller_sql_atomic(repo, client, seat):
    import main
    state, spell, _, path = install(repo, client, seat, 'act-of-treason')
    controller = main.ACTIVE_MATCHES[state.id]
    before = snap(state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
    response = client.post(path + '/action', json={
        'player_id': seat, 'action': request(spell, 'not-an-actual-card')})
    assert response.status_code in (400, 422), response.text
    controller = main.ACTIVE_MATCHES[state.id]
    assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
    assert_private(restore(repo, controller.state))
