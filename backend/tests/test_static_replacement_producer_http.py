"""Real HTTP selected mana payment, retained receipt restart and atomic rejects."""
from copy import deepcopy

import pytest

from game_state.state import Zone, object_incarnation
from tests.test_builtin_metadata_refresh import repo
from tests.generic_import_fixtures import client
from tests.readiness_rules_seam_support import normalize
from tests.test_spell_admission_safety_http import sql_facts
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import SELF, ROWS as BASE, snap
from tests.test_self_graveyard_replacement_interactions import ROWS
from tests.test_self_graveyard_cost_routing import tower_position


def install(repo, client, state):
    import main
    for row in [*BASE.values(), *ROWS.values()]:
        repo.upsert_card(normalize(row))
    deck = [{'card_name': 'Island', 'quantity': 8}]
    response = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck,
                           'sandbox': True, 'controller_a': 'human', 'controller_b': 'human', 'seed': 7221})
    assert response.status_code == 200, response.text
    controller = main.ACTIVE_MATCHES[response.json()['id']]
    state.id = controller.state.id
    controller.state = state
    main._persist_active_match(repo, controller)
    return controller


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
@pytest.mark.parametrize('foreign', [False, True])
def test_actual_http_tower_static_receipt_persists_with_owner_library(repo, client, seat, name, foreign):
    import main
    state, card, tower, _, action = tower_position(seat, name, foreign)
    probe = raw_card(state, ROWS['Psychogenic Probe'], 3-card.owner, Zone.BATTLEFIELD)
    reference = {'incarnation': object_incarnation(card), 'zone_change_sequence': card.zone_change_sequence}
    controller = install(repo, client, state)
    before = snap(state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
    rejected = client.post('/matches/' + state.id + '/action', json={'player_id': 3-seat, 'action': action})
    assert rejected.status_code == 422
    assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
    response = client.post('/matches/' + state.id + '/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    result = controller.state
    assert result.cards[card.id].zone == Zone.LIBRARY
    assert result.players[card.owner].library.count(card.id) == 1
    assert result.cards[tower.id].tapped and result.players[seat].mana_pool.get('B') == 2
    receipt = next(item for item in result.stack if item.source_card_id == probe.id)
    cause = receipt.payload['__shuffle_cause']
    assert cause['kind'] == 'static' and cause['mechanism'] == 'replacement'
    assert cause['source_card_id'] == card.id and cause['source_reference'] == reference
    assert cause['controller'] == seat and cause['source_owner'] == card.owner
    assert 'stack_id' not in cause
    expected = snap(result)
    main.ACTIVE_MATCHES.pop(state.id)
    main._restore_active_matches(repo, state.id)
    assert snap(main.ACTIVE_MATCHES[state.id].state) == expected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
@pytest.mark.parametrize('bad', ['stale', 'foreign', 'duplicate', 'noncreature'])
def test_actual_http_invalid_selected_resource_rejects_full_root_sql(repo, client, seat, name, bad):
    import main
    state, card, tower, _, action = tower_position(seat, name)
    if bad == 'stale':
        state.players[seat].battlefield.remove(card.id)
        card.move_to_zone(Zone.EXILE)
        state.players[seat].exile.append(card.id)
    elif bad == 'foreign':
        action['payment_choices']['sacrifice_card_ids'] = [raw_card(state, BASE[name], 3-seat, Zone.BATTLEFIELD).id]
    elif bad == 'duplicate':
        action['payment_choices']['sacrifice_card_ids'] = [card.id, card.id]
    else:
        action['payment_choices']['sacrifice_card_ids'] = [tower.id]
    controller = install(repo, client, state)
    before = snap(state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
    response = client.post('/matches/' + state.id + '/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 422, response.text
    assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
