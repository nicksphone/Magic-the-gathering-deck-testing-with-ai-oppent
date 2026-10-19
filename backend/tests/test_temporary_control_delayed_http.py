"""Paid public Ray episodes and cold owned SQLite restart; serial slot required."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from game_state.state import Step, Zone
from tests.generic_import_fixtures import client as base_client
from tests.test_builtin_metadata_refresh import repo
from tests.test_batch_graveyard_publication_audit import client, assert_private
from tests.test_temporary_control_lifecycle_audit import ROWS, advance, raw_card, snap
from tests.test_temporary_control_lifecycle_http_audit import install, send, resolve, request, restore
from tests.test_kozilek_graveyard_trigger_audit import FRESH
from tests.test_spell_admission_safety_http import sql_facts


def source_land(state, actor, name):
    row = json.loads((Path(__file__).parents[1] / 'card_data/builtin_oracle_seed.json')
                     .read_text())['cards'][name]
    return raw_card(state, row, actor, Zone.BATTLEFIELD).id


def persist(repo, state):
    import main
    main._persist_active_match(repo, main.ACTIVE_MATCHES[state.id])


def cleanup(client, path, state):
    return advance(state, send=lambda root, actor, action: send(client, path, actor, action))


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_ray_cold_restart_retains_real_cleanup_stack_then_tap_and_repeat(repo, client, seat):
    import main
    state, spell, target, path = install(repo, client, seat, 'ray-of-command', foreign=(seat == 2))
    controller = main.ACTIVE_MATCHES[state.id]
    before = snap(state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
    rejected = client.post(path + '/action', json={'player_id': seat, 'action': request(spell, 'missing')})
    assert rejected.status_code in (400, 422), rejected.text
    assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
    state = send(client, path, seat, request(spell, target))
    assert state.stack[-1].payload['mana_spent'] == 4
    state = resolve(client, path, restore(repo, state))
    record = deepcopy(state.delayed_triggers[-1])
    assert record['controller'] == seat and record['source_card_id'] == spell
    state = cleanup(client, path, restore(repo, state))
    assert state.step == Step.CLEANUP and state.cleanup_repeat_required
    assert not state.cards[target].tapped and state.cards[target].controller == 3-seat
    assert state.stack[-1].effect_key == 'control_loss_tap'
    assert state.stack[-1].controller == seat and state.stack[-1].payload['card_id'] == target
    assert state.stack[-1].payload['__delayed_source_reference'] == record['payload']['__delayed_source_reference']
    assert_private(restore(repo, state))
    state = resolve(client, path, restore(repo, state))
    assert state.cards[target].tapped and not state.stack and not state.delayed_triggers
    state = resolve(client, path, restore(repo, state))
    assert state.step == Step.CLEANUP and not state.cleanup_repeat_required
    assert_private(restore(repo, state))


@pytest.mark.parametrize('seat', [1, 2])
def test_real_paid_http_stifle_can_counter_cleanup_tap_without_undoing_control_expiry(repo, client, seat):
    state, spell, target, path = install(repo, client, seat, 'ray-of-command')
    stifle = raw_card(state, FRESH['Stifle'], seat, Zone.HAND).id
    island = source_land(state, seat, 'Island')
    persist(repo, state)
    state = resolve(client, path, send(client, path, seat, request(spell, target)))
    state = cleanup(client, path, restore(repo, state))
    trigger_id = state.stack[-1].id
    state = send(client, path, seat, {'type': 'tap_land_for_mana', 'card_id': island, 'color': 'U'})
    state = send(client, path, seat, {'type': 'cast_spell', 'card_id': stifle,
                                    'cost_choice': {'id': 'base'}, 'targets': {'target_stack_id': trigger_id}})
    state = resolve(client, path, restore(repo, state))
    assert not state.stack and not state.cards[target].tapped
    assert state.cards[target].controller == 3-seat and state.cards[stifle].zone == Zone.GRAVEYARD
    assert not state.delayed_triggers
    assert_private(restore(repo, state))


@pytest.mark.parametrize('seat', [1, 2])
def test_real_http_cleanup_response_blink_never_taps_new_incarnation(repo, client, seat):
    state, spell, target, path = install(repo, client, seat, 'ray-of-command')
    other = 3-seat
    blink = raw_card(state, ROWS['cloudshift'], other, Zone.HAND).id
    plains = source_land(state, other, 'Plains')
    persist(repo, state)
    state = resolve(client, path, send(client, path, seat, request(spell, target)))
    sequence = state.cards[target].zone_change_sequence
    state = cleanup(client, path, restore(repo, state))
    state = send(client, path, seat, {'type': 'pass_priority'})
    assert state.priority_player == other
    state = send(client, path, other, {'type': 'tap_land_for_mana', 'card_id': plains, 'color': 'W'})
    state = send(client, path, other, request(blink, target))
    state = resolve(client, path, restore(repo, state))
    assert state.cards[target].zone_change_sequence == sequence + 2
    assert state.cards[target].controller == other and not state.cards[target].tapped
    state = resolve(client, path, restore(repo, state))
    assert not state.stack and not state.cards[target].tapped
    assert_private(restore(repo, state))
