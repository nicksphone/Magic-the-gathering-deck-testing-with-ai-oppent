"""Actual typed HTTP continuation and explicit unsupported-body receipts."""
from copy import deepcopy

import pytest

from ai.information import decision_view, is_unknown
from rules_engine.engine import RulesEngine
from tests.test_builtin_metadata_refresh import repo
from tests.generic_import_fixtures import client as base_client
from tests.test_direct_graveyard_bypass_audit import (
    client, install, public_private_restore, main_controller_snapshot,
)
from tests.readiness_rules_seam_support import normalize
from tests.test_spell_admission_safety_http import sql_facts
from tests.test_self_graveyard_replacement_audit import snap, restart
from tests.test_trigger_instruction_compilation_audit import ROWS as PRIMARY_ROWS, FAMILIES, KOZILEK, item_for
from tests.test_trigger_instruction_compilation_http_audit import submit, responses
from tests.test_self_trigger_instruction_product import ROWS, dredge_position, custom, compilation_trace


def seed(repo):
    for row in list(PRIMARY_ROWS.values()) + list(ROWS.values()):
        repo.upsert_card(normalize(row))


def restore_after_public_dredge(repo, client, controller, seat, imp, tmp_path):
    import main
    before = snap(controller.state)
    identifier = controller.state.id
    main.ACTIVE_MATCHES.pop(identifier)
    assert client.get('/matches/' + identifier).status_code == 200
    controller = main.ACTIVE_MATCHES[identifier]
    assert snap(controller.state) == before
    view, _ = decision_view(controller.state, 3-seat, RulesEngine().legal_moves(controller.state, 3-seat))
    assert view.cards[imp].name == 'Stinkweed Imp', 'Publicly witnessed graveyard departure is known memory'
    assert all(is_unknown(view.cards[cid]) for cid in controller.state.players[seat].library)
    assert all(is_unknown(view.cards[cid]) for cid in controller.state.players[seat].hand if cid != imp)
    controller.state = restart(controller.state, tmp_path, 'after-public-dredge')
    assert snap(controller.state) == before
    return controller


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_http_actual_dredge_deliberate_choice_root_sql_privacy_restart(repo, client, seat, name, tmp_path):
    seed(repo)
    state, cid, imp, action = dredge_position(name, seat)
    library, life = list(state.players[seat].library), state.players[seat].life
    controller = install(repo, client, state)
    submit(client, controller, seat, action)
    if name != KOZILEK:
        responses(client, controller)
    responses(client, controller)
    assert controller.state.pending_mechanic_choice['options'] == ['draw', imp]
    controller = public_private_restore(repo, client, controller, seat, tmp_path)
    before = snap(controller.state), deepcopy(main_controller_snapshot(controller)), sql_facts(repo)
    rejected = client.post('/matches/' + state.id + '/action', json={
        'player_id': 3-seat, 'action': {'type': 'choose_mechanic', 'choice_id': imp}})
    assert rejected.status_code == 422, rejected.text
    assert (snap(controller.state), main_controller_snapshot(controller), sql_facts(repo)) == before
    submit(client, controller, seat, {'type': 'choose_mechanic', 'choice_id': imp})
    controller = restore_after_public_dredge(repo, client, controller, seat, imp, tmp_path)
    remaining = 3 if name == KOZILEK else 1
    assert controller.state.players[seat].hand == [imp] + list(reversed(library[-5-remaining:-5]))
    assert set(controller.state.players[seat].graveyard) == set(library[-5:])
    assert controller.state.players[seat].life == life + (2 if name == 'Cloudblazer' else 0)
    assert controller.state.pending_mechanic_choice is None


@pytest.mark.parametrize('seat', [1, 2])
def test_http_genuine_unsupported_compound_no_partial_reward(repo, client, seat, tmp_path):
    seed(repo)
    state, cid, action = custom('Riverwise Augur', seat)
    library, life = list(state.players[seat].library), state.players[seat].life
    controller = install(repo, client, state)
    submit(client, controller, seat, action)
    responses(client, controller)
    item = item_for(controller.state, cid)
    assert item.effect_key == 'noop' and item.payload['__unsupported_trigger_instruction']
    controller = public_private_restore(repo, client, controller, seat, tmp_path)
    responses(client, controller)
    assert not controller.state.players[seat].hand
    assert controller.state.players[seat].library == library and controller.state.players[seat].life == life
    assert controller.state.pending_mechanic_choice is None
