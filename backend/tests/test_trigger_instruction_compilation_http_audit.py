"""Actual ASGI paid actions on exclusive memory/file repositories."""
from copy import deepcopy

import pytest

from game_state.state import Zone
from tests.test_builtin_metadata_refresh import repo
from tests.generic_import_fixtures import client as base_client
from tests.readiness_rules_seam_support import normalize
from tests.test_direct_graveyard_bypass_audit import (
    client, install, main_controller_snapshot, public_private_restore,
)
from tests.test_spell_admission_safety_http import sql_facts
from tests.test_self_graveyard_replacement_audit import snap
from tests.test_trigger_instruction_compilation_audit import (
    ROWS, FAMILIES, KOZILEK, position, item_for, compilation_trace,
)


def submit(client, controller, actor, action):
    response = client.post('/matches/' + controller.state.id + '/action',
                           json={'player_id': actor, 'action': action})
    assert response.status_code == 200, response.text


def responses(client, controller):
    for _ in range(2):
        submit(client, controller, controller.state.priority_player, {'type': 'pass_priority'})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_http_paid_complete_trigger_cold_restore_private_resolution(repo, client, seat, name, tmp_path):
    for row in ROWS.values():
        repo.upsert_card(normalize(row))
    state, cid, action = position(name, seat)
    library, life = list(state.players[seat].library), state.players[seat].life
    controller = install(repo, client, state)
    submit(client, controller, seat, action)
    if name != KOZILEK:
        responses(client, controller)
    assert item_for(controller.state, cid).controller == seat
    controller = public_private_restore(repo, client, controller, seat, tmp_path)
    responses(client, controller)
    controller = public_private_restore(repo, client, controller, seat, tmp_path)
    count = 4 if name == KOZILEK else 2
    assert controller.state.players[seat].hand == list(reversed(library[-count:])), 'HTTP must execute the printed draw count'
    assert controller.state.players[seat].life == life + (2 if name == 'Cloudblazer' else 0)
    assert controller.state.cards[cid].zone == (Zone.STACK if name == KOZILEK else Zone.BATTLEFIELD)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('bad', ['wrong_actor', 'underpaid'])
def test_http_invalid_cast_full_root_controller_sql_unchanged(repo, client, seat, name, bad):
    for row in ROWS.values():
        repo.upsert_card(normalize(row))
    state, _, action = position(name, seat)
    if bad == 'underpaid':
        state.players[seat].mana_pool = {}
    controller = install(repo, client, state)
    before = snap(controller.state), deepcopy(main_controller_snapshot(controller)), sql_facts(repo)
    response = client.post('/matches/' + state.id + '/action', json={
        'player_id': 3-seat if bad == 'wrong_actor' else seat, 'action': action})
    assert response.status_code == 422, response.text
    assert (snap(controller.state), main_controller_snapshot(controller), sql_facts(repo)) == before
